from flask import Flask, render_template, jsonify, request, abort
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import Pinecone
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from src.prompt import *
from config import get_config
import os
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

# Get configuration
config = get_config()

# Configure logging
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler = RotatingFileHandler(
    config.LOG_FILE,
    maxBytes=config.LOG_MAX_BYTES,
    backupCount=config.LOG_BACKUP_COUNT
)
log_handler.setFormatter(log_formatter)
logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

# Create Flask app
app = Flask(__name__)
app.config.from_object(config)

# Security headers
# Force HTTPS only in production, allow specific external CDNs and images in CSP
csp = {
    'default-src': "'self'",
    'style-src': [
        "'self'",
        'https://stackpath.bootstrapcdn.com',
        'https://use.fontawesome.com'
    ],
    'script-src': [
        "'self'",
        'https://ajax.googleapis.com'
    ],
    'img-src': [
        "'self'",
        'https://cdn-icons-png.flaticon.com',
        'https://i.ibb.co'
    ]
}

Talisman(
    app,
    content_security_policy=csp,
    force_https=not config.DEBUG
)
app.config['JSON_SORT_KEYS'] = False

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[config.RATELIMIT_DEFAULT],
    storage_uri=config.RATELIMIT_STORAGE_URL,
)

PINECONE_API_KEY = config.PINECONE_API_KEY
GEMINI_API_KEY = config.GEMINI_API_KEY

if not PINECONE_API_KEY or not GEMINI_API_KEY:
    logger.error("Missing required API keys in environment variables")
    raise ValueError("Please set PINECONE_API_KEY and GEMINI_API_KEY in .env file")

try:
    embeddings = download_hugging_face_embeddings()
    logger.info("Embeddings model loaded successfully")
    
    # Connect to Pinecone
    docsearch = Pinecone.from_existing_index(
        index_name=config.PINECONE_INDEX,
        embedding=embeddings
    )
    logger.info(f"Connected to Pinecone index: {config.PINECONE_INDEX}")
    
    # Initialize retriever
    retriever = docsearch.as_retriever(
        search_type=config.RETRIEVER_SEARCH_TYPE,
        search_kwargs={"k": config.RETRIEVER_K}
    )
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        temperature=config.GEMINI_TEMPERATURE,
        max_tokens=config.GEMINI_MAX_TOKENS,
        google_api_key=GEMINI_API_KEY
    )
    logger.info("Gemini model initialized successfully")
except Exception as e:
    logger.error(f"Initialization error: {str(e)}", exc_info=True)
    raise

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route("/")
def index():
    return render_template('chat.html')


@app.route("/get", methods=["POST"])
@limiter.limit("30/minute")
def chat():
    try:
        msg = request.form.get("msg", "").strip()
        
        # Validate message
        if not msg:
            return jsonify({"error": "Please enter a message"}), 400
        
        if len(msg) < config.MIN_MESSAGE_LENGTH:
            return jsonify({"error": f"Message must be at least {config.MIN_MESSAGE_LENGTH} character"}), 400
        
        if len(msg) > config.MAX_MESSAGE_LENGTH:
            return jsonify({"error": f"Message too long. Please keep it under {config.MAX_MESSAGE_LENGTH} characters."}), 400
        
        logger.info("Processing user question")
        
        # Get relevant documents
        docs = retriever.invoke(msg)
        logger.info(f"Retrieved {len(docs)} documents")
        
        if not docs:
            logger.warning("No documents retrieved from Pinecone")
            return jsonify({
                "answer": "I couldn't find relevant information to answer your question. "
                         "Please try rephrasing or consult with a healthcare professional."
            }), 200
        
        context = "\n\n".join([doc.page_content for doc in docs])
        full_prompt = system_prompt.replace("{context}", context) + f"\n\nQuestion: {msg}\n\nAnswer:"
        
        # Get response from LLM
        response = llm.invoke(full_prompt)
        answer = response.content
        
        logger.info("Response generated successfully")
        return jsonify({"answer": str(answer)}), 200
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": "An error occurred while processing your request. Please try again."}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit errors"""
    logger.warning(f"Rate limit exceeded: {str(e)}")
    return jsonify({"error": "Too many requests. Please try again later."}), 429

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning(f"404 error: {request.path}")
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"500 error: {str(error)}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    debug_mode = os.environ.get("FLASK_ENV") == "development"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
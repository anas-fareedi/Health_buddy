from dotenv import load_dotenv
import os
import sys

# When running directly (python app.py), force development mode BEFORE
# load_dotenv() so the .env value of FLASK_ENV=production cannot activate
# Talisman's HTTPS redirect on the local dev server.
# load_dotenv() respects existing env vars by default (override=False).
if not os.environ.get("_FLASK_ENV_LOCKED"):
    os.environ["FLASK_ENV"] = "development"
    os.environ["_FLASK_ENV_LOCKED"] = "1"

# Load environment variables (will NOT overwrite FLASK_ENV we just set)
load_dotenv()

from flask import Flask, render_template, jsonify, request, abort
from flask.json.provider import DefaultJSONProvider
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.helper import download_hugging_face_embeddings
from langchain_pinecone import Pinecone
from langchain_google_genai import ChatGoogleGenerativeAI
from src.prompt import *
from config import get_config
import logging
from logging.handlers import RotatingFileHandler

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

# Determine environment — default to development for local runs.
# .env may have FLASK_ENV=production which would activate Talisman and
# break local HTTP access, so we respect it ONLY when explicitly intended.
_flask_env = os.environ.get("FLASK_ENV", "development")
print(f"[STARTUP] FLASK_ENV = {_flask_env!r}")

# Only apply Talisman security headers in production.
# In development the Flask dev server has no SSL certificate, so Talisman
# would force HTTPS → ERR_SSL_PROTOCOL_ERROR / WRONG_VERSION_NUMBER.
# Additionally, once Talisman sets HSTS headers the browser caches them and
# ALL future requests on that host:port are auto-upgraded to HTTPS even after
# Talisman is removed.  Changing the port is the only way to escape the cache.
if _flask_env == "production":
    force_https = os.environ.get("FORCE_HTTPS", "false").lower() == "true"
    Talisman(
        app,
        content_security_policy=csp,
        force_https=force_https
    )
    print(f"[STARTUP] Talisman ENABLED  (force_https={force_https})")
else:
    print("[STARTUP] Talisman DISABLED (development mode)")


# Flask 3.x removed JSON_SORT_KEYS config key — use DefaultJSONProvider instead
DefaultJSONProvider.sort_keys = False

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
    # HARDCODE port 5000 for local dev — do NOT read from PORT env var.
    # Port 8080 (from .env) has a poisoned HSTS cache in the browser from
    # prior Talisman runs, causing ERR_SSL_PROTOCOL_ERROR on every request.
    port = 5000
    print(f"[STARTUP] Server starting on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
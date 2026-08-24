import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from flask import Flask, render_template, jsonify, request, abort, Response, stream_with_context
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

if config.FLASK_ENV == "production":
    # Production (Render): log to stdout — Render captures it automatically.
    # File logging is pointless on ephemeral containers and causes PermissionError
    # when running as non-root user.
    log_handler = logging.StreamHandler(sys.stdout)
else:
    # Development: log to rotating file
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

# Security headers — must whitelist all CDN domains used in chat.html
csp = {
    'default-src': "'self'",
    'style-src': [
        "'self'",
        "'unsafe-inline'",
        'https://fonts.googleapis.com',
        'https://cdnjs.cloudflare.com',
        'https://cdn.jsdelivr.net',
        'https://stackpath.bootstrapcdn.com',
        'https://use.fontawesome.com'
    ],
    'font-src': [
        "'self'",
        'https://fonts.gstatic.com',
        'https://cdnjs.cloudflare.com',
        'https://use.fontawesome.com'
    ],
    'script-src': [
        "'self'",
        'https://cdn.jsdelivr.net',
        'https://cdnjs.cloudflare.com',
        'https://ajax.googleapis.com'
    ],
    'img-src': [
        "'self'",
        'https://cdn-icons-png.flaticon.com',
        'https://i.ibb.co',
        'data:'
    ]
}

_flask_env = os.environ.get("FLASK_ENV", "development")
print(f"[STARTUP] FLASK_ENV = {_flask_env!r}")

if _flask_env == "production":
    force_https = os.environ.get("FORCE_HTTPS", "false").lower() == "true"
    Talisman(
        app,
        content_security_policy=csp,
        force_https=force_https
    )
    print(f"[STARTUP] Talisman ENABLED (force_https={force_https})")
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

# Lazy Model & Retriever Instances
_embeddings = None
_retriever = None
_llm = None

def get_retriever():
    global _embeddings, _retriever
    if _retriever is None:
        logger.info("Lazy initializing embeddings & Pinecone vector retriever...")
        PINECONE_API_KEY = config.PINECONE_API_KEY
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY missing in environment variables")
        
        _embeddings = download_hugging_face_embeddings()
        docsearch = Pinecone.from_existing_index(
            index_name=config.PINECONE_INDEX,
            embedding=_embeddings
        )
        _retriever = docsearch.as_retriever(
            search_type=config.RETRIEVER_SEARCH_TYPE,
            search_kwargs={"k": config.RETRIEVER_K}
        )
        logger.info("Pinecone retriever initialized successfully")
    return _retriever

def get_llm():
    global _llm
    if _llm is None:
        logger.info("Lazy initializing Gemini LLM model...")
        GEMINI_API_KEY = config.GEMINI_API_KEY
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY missing in environment variables")
            
        _llm = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            temperature=config.GEMINI_TEMPERATURE,
            max_tokens=config.GEMINI_MAX_TOKENS,
            google_api_key=GEMINI_API_KEY
        )
        logger.info("Gemini model initialized successfully")
    return _llm

@app.route("/health", methods=["GET"])
def health():
    """Lightweight health check endpoint for deployment port probes."""
    return jsonify({"status": "healthy"}), 200


@app.route("/")
def index():
    return render_template('chat.html')


@app.route("/debug-env", methods=["GET"])
def debug_env():
    """Diagnostic endpoint — reports whether required env vars are present (not their values)."""
    keys = ["PINECONE_API_KEY", "GEMINI_API_KEY", "HF_TOKEN", "PINECONE_INDEX", "FLASK_ENV", "SECRET_KEY"]
    status = {}
    for k in keys:
        val = os.environ.get(k)
        if val:
            status[k] = f"SET ({len(val)} chars)"
        else:
            status[k] = "MISSING"
    return jsonify(status), 200


@app.route("/get_stream", methods=["POST"])
@limiter.limit("30/minute")
def chat_stream():
    """Stream real-time LLM tokens and PDF document source citations via SSE."""
    msg = request.form.get("msg", "").strip()
    
    if not msg:
        return jsonify({"error": "Please enter a question."}), 400
    
    if len(msg) < config.MIN_MESSAGE_LENGTH:
        return jsonify({"error": f"Message must be at least {config.MIN_MESSAGE_LENGTH} character"}), 400
    
    if len(msg) > config.MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Message too long. Keep under {config.MAX_MESSAGE_LENGTH} characters."}), 400

    def generate():
        try:
            retriever = get_retriever()
            llm = get_llm()
            
            logger.info("Retrieving documents for streaming user query")
            docs = retriever.invoke(msg)
            logger.info(f"Retrieved {len(docs)} documents from Pinecone")
            
            # Format source document citations
            sources = []
            if docs:
                for idx, doc in enumerate(docs, 1):
                    raw_src = doc.metadata.get("source", "Medical Reference PDF")
                    src_filename = os.path.basename(str(raw_src))
                    page_num = doc.metadata.get("page")
                    page_label = f", Page {int(page_num) + 1}" if page_num is not None else ""
                    snippet = doc.page_content[:160].strip().replace("\n", " ") + "..."
                    
                    sources.append({
                        "id": idx,
                        "title": f"{src_filename}{page_label}",
                        "snippet": snippet
                    })
            
            # Send initial sources payload
            yield f"event: sources\ndata: {json.dumps({'sources': sources})}\n\n"
            
            if not docs:
                fallback_msg = "I couldn't find relevant medical information in the PDF database for your question. Please consult a healthcare professional."
                yield f"event: token\ndata: {json.dumps({'token': fallback_msg})}\n\n"
                yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"
                return
            
            context = "\n\n".join([f"[Source {i+1}]: {doc.page_content}" for i, doc in enumerate(docs)])
            full_prompt = system_prompt.replace("{context}", context) + f"\n\nUser Question: {msg}\n\nAnswer:"
            
            logger.info("Streaming Gemini LLM tokens...")
            for chunk in llm.stream(full_prompt):
                if chunk.content:
                    yield f"event: token\ndata: {json.dumps({'token': chunk.content})}\n\n"
            
            yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"
            logger.info("Token streaming completed successfully")
            
        except Exception as e:
            logger.error(f"Error in streaming endpoint: {str(e)}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': 'An error occurred while streaming the answer. Please try again.'})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")


@app.route("/get", methods=["POST"])
@limiter.limit("30/minute")
def chat():
    try:
        msg = request.form.get("msg", "").strip()
        
        if not msg:
            return jsonify({"error": "Please enter a message"}), 400
        
        if len(msg) < config.MIN_MESSAGE_LENGTH or len(msg) > config.MAX_MESSAGE_LENGTH:
            return jsonify({"error": "Invalid message length"}), 400
        
        retriever = get_retriever()
        llm = get_llm()
        
        docs = retriever.invoke(msg)
        if not docs:
            return jsonify({"answer": "I couldn't find relevant information in the medical database."}), 200
        
        context = "\n\n".join([doc.page_content for doc in docs])
        full_prompt = system_prompt.replace("{context}", context) + f"\n\nQuestion: {msg}\n\nAnswer:"
        
        response = llm.invoke(full_prompt)
        return jsonify({"answer": str(response.content)}), 200
        
    except Exception as e:
        logger.error(f"Error in chat endpoint [{type(e).__name__}]: {str(e)}", exc_info=True)
        return jsonify({"error": f"Server error: {type(e).__name__}: {str(e)}"}), 500


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
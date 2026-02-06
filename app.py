from flask import Flask, render_template, jsonify, request
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import Pinecone
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from src.prompt import *
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

load_dotenv()

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not PINECONE_API_KEY or not GEMINI_API_KEY:
    logger.error("Missing API keys in environment variables")
    raise ValueError("Please set PINECONE_API_KEY and GEMINI_API_KEY in .env file")

try:
    embeddings = download_hugging_face_embeddings()
    logger.info("Embeddings model loaded successfully")
    
    index_name = "medicalbot"
    
    # Embed each chunk and upsert the embeddings into your Pinecone index.
    docsearch = Pinecone.from_existing_index(
        index_name=index_name,
        embedding=embeddings
    )
    logger.info(f"Connected to Pinecone index: {index_name}")
    
    retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k":3})
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.1, max_tokens=6000)
    logger.info("Gemini model initialized successfully")
except Exception as e:
    logger.error(f"Initialization error: {str(e)}")
    raise

@app.route("/")
def index():
    return render_template('chat.html')

@app.route("/get", methods=["POST"])
def chat():
    try:
        msg = request.form.get("msg", "").strip()
        
        if not msg:
            return "Please enter a message.", 400
        
        if len(msg) > 1000:
            return "Message too long. Please keep it under 1000 characters.", 400
        
        logger.info(f"User question: {msg}")
        
        # Get relevant documents
        logger.info("Retrieving relevant documents from Pinecone...")
        docs = retriever.invoke(msg)
        logger.info(f"Retrieved {len(docs)} documents")
        
        if not docs:
            logger.warning("No documents retrieved from Pinecone")
            return "I couldn't find relevant information to answer your question. Please try rephrasing."
        
        context = "\n\n".join([doc.page_content for doc in docs])
        logger.info(f"Context length: {len(context)} characters")
        
        full_prompt = system_prompt.replace("{context}", context) + f"\n\nQuestion: {msg}\n\nAnswer:"
        
        # Get response from LLM
        logger.info("Calling Gemini API...")
        response = llm.invoke(full_prompt)
        answer = response.content
        
        logger.info(f"Response generated successfully: {answer[:100]}...")
        return str(answer)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return f"Sorry, I encountered an error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)
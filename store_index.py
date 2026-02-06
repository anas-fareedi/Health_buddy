from src.helper import load_pdf_file, text_split, download_hugging_face_embeddings
from pinecone.grpc import PineconeGRPC as PineconeClient
from pinecone import ServerlessSpec
from langchain_pinecone import Pinecone
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')

if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY not found in environment variables. Please check your .env file.")

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

try:
    logger.info("Loading PDF files from Data/ directory...")
    extracted_data = load_pdf_file(data='Data/')
    logger.info(f"Loaded {len(extracted_data)} documents")
    
    logger.info("Splitting text into chunks...")
    text_chunks = text_split(extracted_data)
    logger.info(f"Created {len(text_chunks)} text chunks")
    
    logger.info("Loading embeddings model...")
    embeddings = download_hugging_face_embeddings()
    logger.info("Embeddings model loaded successfully")
except Exception as e:
    logger.error(f"Error during data preparation: {str(e)}")
    raise

try:
    pc = PineconeClient(api_key=PINECONE_API_KEY)
    
    index_name = "medicalbot"
    
    # Check if index already exists
    existing_indexes = [index.name for index in pc.list_indexes()]
    
    if index_name in existing_indexes:
        logger.warning(f"Index '{index_name}' already exists. Deleting old index...")
        pc.delete_index(index_name)
        logger.info(f"Old index '{index_name}' deleted")
    
    logger.info(f"Creating new index '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=384, 
        metric="cosine", 
        spec=ServerlessSpec(
            cloud="aws", 
            region="us-east-1"
        ) 
    )
    logger.info(f"Index '{index_name}' created successfully")
    
    # Embed each chunk and upsert the embeddings into your Pinecone index.
    logger.info("Upserting embeddings to Pinecone...")
    docsearch = Pinecone.from_documents(
        documents=text_chunks,
        index_name=index_name,
        embedding=embeddings, 
    )
    logger.info("Embeddings uploaded to Pinecone successfully!")
    logger.info(f"Total vectors stored: {len(text_chunks)}")
    
except Exception as e:
    logger.error(f"Error during Pinecone operations: {str(e)}")
    raise
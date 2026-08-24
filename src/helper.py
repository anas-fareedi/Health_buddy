import os
from typing import List
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Extract Data From the PDF File
def load_pdf_file(data: str) -> List:
    """Load all PDF files from the target directory."""
    if not os.path.exists(data):
        raise FileNotFoundError(f"Data path '{data}' does not exist.")
    
    loader = DirectoryLoader(
        data,
        glob="*.pdf",
        loader_cls=PyPDFLoader
    )
    documents = loader.load()
    return documents

# Split the Data into Text Chunks
def text_split(extracted_data: List) -> List:
    """Split documents into text chunks for vector embeddings."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    text_chunks = text_splitter.split_documents(extracted_data)
    return text_chunks

# Download the Embeddings from HuggingFace 
def download_hugging_face_embeddings():
    """Initialize embeddings model (384 dimensions). Try HuggingFace Endpoint if token set, else load local HuggingFaceEmbeddings model."""
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        try:
            from langchain_huggingface import HuggingFaceEndpointEmbeddings
            return HuggingFaceEndpointEmbeddings(
                model="sentence-transformers/all-MiniLM-L6-v2",
                huggingfacehub_api_token=hf_token
            )
        except Exception:
            pass

    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
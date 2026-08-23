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
    """Initialize embeddings model (384 dimensions). Uses HF Inference API if HF_TOKEN is set, else lazy loads local model.
    
    On Render (512MB RAM), PyTorch cannot be loaded locally — HF_TOKEN is required.
    """
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        from langchain_huggingface import HuggingFaceEndpointEmbeddings
        # Do NOT catch exceptions here — if the API fails, we want a loud error
        # instead of silently falling back to the local model (which OOMs on Render).
        return HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            huggingfacehub_api_token=hf_token
        )

    # Fallback: load model locally (requires torch + sentence-transformers)
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
    except ImportError:
        raise RuntimeError(
            "HF_TOKEN is not set and torch/sentence-transformers are not installed. "
            "On Render's free tier, set HF_TOKEN to use the HuggingFace Inference API. "
            "Get a free token at https://huggingface.co/settings/tokens"
        )
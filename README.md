# Health_buddy (End-to-end-Medical-Chatbot-Generative-AI)

## future enhancements 
### (adding bean-balance feature) 
Track food and lifestyle for kidney disease
 
A medical chatbot powered by Google Gemini AI and Pinecone vector database for intelligent question-answering based on medical documents.

## Features

- 🤖 Powered by Google Gemini AI (gemini-2.0-flash-exp)
- 📚 RAG (Retrieval-Augmented Generation) for accurate medical information
- 🔍 Semantic search using Pinecone vector database
- 💬 Clean and responsive chat interface
- ⚡ Real-time responses with loading indicators
- 🛡️ Input validation and error handling

### Images

<img width="1826" height="894" alt="Screenshot 2026-02-06 205215" src="https://github.com/user-attachments/assets/af358638-488b-4434-93f8-9d009c48f209" />

# How to run?
### STEPS:

Clone the repository

```bash
git clone <your-repo-url>
cd End-to-end-Medical-Chatbot
```

### STEP 01- Create a conda environment after opening the repository

```bash
conda create -n medibot python=3.10 -y
```

```bash
conda activate medibot
```


### STEP 02- Install the requirements
```bash
pip install -r requirements.txt
```


### STEP 03- Create a `.env` file in the root directory and add your Pinecone & Gemini credentials as follows:

```ini
PINECONE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**How to get API keys:**
- Pinecone: Sign up at [https://www.pinecone.io/](https://www.pinecone.io/)
- Gemini: Get your API key from [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)


### STEP 04- Add your medical PDF documents to the `Data/` folder


### STEP 05- Run the following command to create embeddings and store them in Pinecone

```bash
python store_index.py
```

This will:
- Load PDF files from the Data/ folder
- Split them into chunks
- Create embeddings using HuggingFace
- Upload to Pinecone vector database


### STEP 06- Finally run the Flask application

```bash
python app.py
```

Now open your browser and navigate to:
```
http://localhost:8080
```

## Project Structure

```
End-to-end-Medical-Chatbot/
├── app.py                  # Flask application
├── store_index.py          # Script to create and store embeddings
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
├── Data/                   # Place your PDF files here
├── src/
│   ├── helper.py          # Helper functions for PDF loading and embeddings
│   └── prompt.py          # System prompts for the chatbot
├── templates/
│   └── chat.html          # Chat interface
└── static/
    └── style.css          # Styling
```

## Technologies Used

- **Google Gemini AI** - Large Language Model
- **Pinecone** - Vector database for semantic search
- **LangChain** - Framework for LLM applications
- **HuggingFace** - Sentence transformers for embeddings
- **Flask** - Web framework
- **Bootstrap** - Frontend styling


### Techstack Used:

- Python
- LangChain
- Flask
- GPT
- Pinecone

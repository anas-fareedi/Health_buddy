from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="health-buddy",
    version="1.0.0",
    author="Anas Fareedi",
    author_email="anasfareedi786786@gmail.com",
    description="A medical chatbot powered by LangChain, Pinecone, and Google Gemini",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/Health-buddy",
    packages=find_packages(exclude=["tests", "research"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.10",
    install_requires=[
        "Flask==3.0.0",
        "Flask-Talisman==1.1.0",
        "python-dotenv==1.0.0",
        "langchain==0.1.0",
        "langchain-core==0.1.0",
        "langchain-community==0.0.20",
        "langchain-text-splitters==0.0.1",
        "langchain-pinecone==0.1.0",
        "langchain-google-genai==0.0.14",
        "langchain-huggingface==0.0.48",
        "pinecone-client==3.0.0",
        "sentence-transformers==2.2.2",
        "google-generativeai==0.3.0",
        "pypdf==4.0.1",
        "huggingface-hub==0.20.0",
        "torch==2.1.0",
        "gunicorn==21.2.0",
        "flask-limiter==3.5.0",
        "Werkzeug==3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest==7.4.0",
            "pytest-cov==4.1.0",
            "black==23.10.0",
            "flake8==6.1.0",
            "mypy==1.6.0",
        ],
    },
)

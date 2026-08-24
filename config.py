import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get("SECRET_KEY", "health-buddy-production-secret-key-default")
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = False
    TESTING = False
    
    # API Configuration
    PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    
    # Model Configuration
    PINECONE_INDEX = os.environ.get("PINECONE_INDEX", "medicalbot")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    GEMINI_TEMPERATURE = 0.1
    GEMINI_MAX_TOKENS = 6000
    
    # Vector Retrieval Configuration
    RETRIEVER_SEARCH_TYPE = "similarity"
    RETRIEVER_K = 3
    
    # Message Configuration
    MAX_MESSAGE_LENGTH = 1000
    MIN_MESSAGE_LENGTH = 1
    
    # Logging
    LOG_FILE = "app.log"
    LOG_MAX_BYTES = 10485760  # 10MB
    LOG_BACKUP_COUNT = 10
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate Limiting (requests per hour)
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "100/hour"
    RATELIMIT_STORAGE_URL = os.environ.get("REDIS_URL", "memory://")


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    def __init__(self):
        super().__init__()
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set in production")



class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    RATELIMIT_ENABLED = False


def get_config():
    """Get configuration based on FLASK_ENV"""
    env = os.environ.get("FLASK_ENV", "development")
    
    if env == "development":
        return DevelopmentConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return ProductionConfig()

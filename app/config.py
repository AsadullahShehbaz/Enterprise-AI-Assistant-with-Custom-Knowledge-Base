# app/config.py
"""
Application configuration from environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env file."""
    
    # App
    APP_NAME: str = "Persistent Chatbot API"
    DEBUG: bool = False
    GEMINI_API_KEY : str
    # Database
    DATABASE_URL: str
    
    # Security
    SECRET_KEY: str
    # JWT_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI/LLM
    GROQ_API_KEY: str = ""
    
    # Google Search (Optional)
    GOOGLE_API_KEY: str = ""
    GOOGLE_CSE_ID: str = ""
    
    # Vector Store - FAISS
    FAISS_PERSIST_DIRECTORY: str = "./faiss_db"
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to avoid re-reading .env file on every call.
    
    Returns:
        Settings: Application configuration
    """
    return Settings()
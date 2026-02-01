# backend/app/config.py
"""
Configuration settings for ROS Code Intelligence Platform
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    APP_NAME: str = "ROS Code Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # CORS Settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]
    
    # File Upload Settings
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100 MB
    ALLOWED_EXTENSIONS: List[str] = [".zip"]
    
    # Directory Settings
    BASE_UPLOAD_DIR: Path = Path("uploads")
    TEMP_EXTRACT_DIR: Path = Path("extracted_projects")
    
    # Parser Settings
    RELEVANT_EXTENSIONS: List[str] = [
        ".py", ".cpp", ".c", ".h", ".hpp",
        ".launch", ".xml", ".yaml", ".yml"
    ]
    
    IGNORED_PATHS: List[str] = [
        "/build/", "/devel/", "/install/", 
        "/log/", "/__pycache__/", ".pyc", ".pyo"
    ]
    
    # Cache Settings
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 3600  # 1 hour in seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
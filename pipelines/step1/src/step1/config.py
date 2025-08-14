"""Configuration module for loading and validating environment variables."""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Number of recent days to search for articles
    recent_days: int = Field(default=180, env="RECENT_DAYS")
    
    # Email for Crossref API (optional)
    email_for_crossref: Optional[str] = Field(default=None, env="EMAIL_FOR_CROSSREF")
    
    # Maximum number of results to fetch
    max_results: int = Field(default=200, env="MAX_RESULTS")
    
    # Whether to allow protocol papers
    allow_protocols: bool = Field(default=False, env="ALLOW_PROTOCOLS")
    
    # Whether to allow pediatric studies
    allow_pediatric: bool = Field(default=True, env="ALLOW_PEDIATRIC")
    
    # Extra query terms to add to the search
    extra_query: Optional[str] = Field(default=None, env="EXTRA_QUERY")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a global settings instance
settings = Settings()
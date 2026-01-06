"""
Application configuration using Pydantic Settings.
Loads from environment variables with .env file support.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # API Keys
    anthropic_api_key: str = ""
    
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/autoapply_db"
    database_url_sync: str = "postgresql://user:password@localhost:5432/autoapply_db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    
    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    # Scraping Configuration
    max_scraping_pages: int = 10
    scraping_delay_min: int = 2
    scraping_delay_max: int = 5
    use_proxy: bool = False
    proxy_url: Optional[str] = None
    
    # AI Configuration
    claude_sonnet_model: str = "claude-sonnet-4-20250514"
    claude_opus_model: str = "claude-opus-4-20250514"
    max_tokens_jd_analysis: int = 2000
    max_tokens_resume_tailor: int = 4000
    max_tokens_cover_letter: int = 2000
    
    # Cost Tracking
    cost_alert_threshold_usd: float = 50.0
    daily_budget_usd: float = 20.0
    
    # File Storage
    resumes_dir: str = "data/resumes"
    cover_letters_dir: str = "data/cover_letters"
    scraped_jobs_dir: str = "data/scraped_jobs"
    
    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # LinkedIn
    linkedin_session_cookie: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

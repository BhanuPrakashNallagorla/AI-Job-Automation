"""
Configuration using Pydantic Settings.
Supports both Anthropic and Gemini APIs.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # AI API Keys
    gemini_api_key: str = ""
    anthropic_api_key: str = ""  # Legacy, kept for compatibility
    
    # Scraper API Keys (for real job data)
    serper_api_key: str = ""      # Serper.dev - 2500 free/month (RECOMMENDED)
    rapidapi_key: str = ""         # RapidAPI/JSearch - 150 free/month
    scrapingbee_api_key: str = ""  # ScrapingBee - 1000 credits
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./autoapply.db"
    database_url_sync: str = "sqlite:///./autoapply.db"
    
    # Redis (optional)
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 604800  # 7 days
    
    # Gemini Rate Limits
    max_daily_requests: int = 1400  # Buffer below 1500
    rate_limit_rpm: int = 14  # Buffer below 15
    
    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    cors_origins: List[str] = ["*"]
    
    # Scraping
    max_scraping_pages: int = 10
    scraping_delay_min: int = 2
    scraping_delay_max: int = 5
    use_proxy: bool = False
    proxy_url: Optional[str] = None
    
    # Legacy AI settings (kept for compatibility)
    claude_sonnet_model: str = "claude-sonnet-4-20250514"
    claude_opus_model: str = "claude-opus-4-20250514"
    max_tokens_jd_analysis: int = 2000
    max_tokens_resume_tailor: int = 4000
    max_tokens_cover_letter: int = 2000
    
    # Cost/Budget (Gemini is free, but track usage)
    cost_alert_threshold_usd: float = 0.0
    daily_budget_usd: float = 0.0  # Not applicable for free tier
    
    # File Storage
    resumes_dir: str = "data/resumes"
    cover_letters_dir: str = "data/cover_letters"
    scraped_jobs_dir: str = "data/scraped_jobs"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "console"
    
    # LinkedIn Session
    linkedin_session_cookie: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Singleton for backward compatibility
settings = get_settings()

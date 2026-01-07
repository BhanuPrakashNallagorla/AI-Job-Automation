"""
Scrapers module - Real job data only.
Uses Serper.dev API for Google Jobs data.
"""
# Real scraper
from scrapers.serper_scraper import SerperJobScraper

# Manager
from scrapers.scraper_manager import ScraperManager

__all__ = [
    "SerperJobScraper",
    "ScraperManager",
]

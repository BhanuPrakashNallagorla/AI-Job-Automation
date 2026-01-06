"""
Scrapers module initialization.
"""
from scrapers.base_scraper import BaseScraper
from scrapers.naukri_scraper import NaukriScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.instahire_scraper import InstahireScraper

__all__ = [
    "BaseScraper",
    "NaukriScraper",
    "LinkedInScraper",
    "InstahireScraper",
]

"""
Tests for scraper components.
"""
import pytest
from scrapers.base_scraper import BaseScraper


def test_salary_parsing():
    """Test salary string parsing."""
    # LPA format
    assert BaseScraper.parse_salary("10-15 LPA") == {"min": 1000000, "max": 1500000}
    assert BaseScraper.parse_salary("25L") == {"min": 2500000, "max": 2500000}
    
    # Plain numbers (assume INR)
    assert BaseScraper.parse_salary("1000000-1500000") == {"min": 1000000, "max": 1500000}
    
    # Empty/None
    assert BaseScraper.parse_salary(None) == {"min": None, "max": None}
    assert BaseScraper.parse_salary("") == {"min": None, "max": None}


def test_experience_parsing():
    """Test experience string parsing."""
    # Range format
    assert BaseScraper.parse_experience("3-5 years") == {"min": 3, "max": 5}
    
    # Plus format
    assert BaseScraper.parse_experience("5+ years") == {"min": 5, "max": None}
    
    # Single number
    assert BaseScraper.parse_experience("5 years") == {"min": 5, "max": 5}
    
    # Empty/None
    assert BaseScraper.parse_experience(None) == {"min": None, "max": None}


def test_text_cleaning():
    """Test text cleaning utility."""
    # Multiple spaces
    assert BaseScraper.clean_text("  hello   world  ") == "hello world"
    
    # Newlines and tabs
    assert BaseScraper.clean_text("hello\n\tworld") == "hello world"
    
    # None
    assert BaseScraper.clean_text(None) == ""


def test_naukri_scraper_url_building():
    """Test Naukri URL building."""
    from scrapers.naukri_scraper import NaukriScraper
    
    scraper = NaukriScraper.__new__(NaukriScraper)
    
    # Basic search
    url = scraper.build_search_url(keyword="python developer")
    assert "python-developer" in url
    assert "naukri.com" in url
    
    # With location
    url = scraper.build_search_url(keyword="ml engineer", location="bangalore")
    assert "ml-engineer" in url
    assert "bangalore" in url
    
    # With pagination
    url = scraper.build_search_url(keyword="python", page=3)
    assert "pageNo=3" in url


def test_linkedin_scraper_url_building():
    """Test LinkedIn URL building."""
    from scrapers.linkedin_scraper import LinkedInScraper
    
    scraper = LinkedInScraper.__new__(LinkedInScraper)
    
    # Basic search
    url = scraper.build_search_url(keyword="software engineer")
    assert "linkedin.com/jobs/search" in url
    assert "keywords=software+engineer" in url
    
    # With location
    url = scraper.build_search_url(keyword="data scientist", location="Bangalore")
    assert "location=Bangalore" in url
    
    # With remote filter
    url = scraper.build_search_url(keyword="developer", remote=True)
    assert "f_WT=2" in url


def test_instahire_scraper_url_building():
    """Test Instahire URL building."""
    from scrapers.instahire_scraper import InstahireScraper
    
    scraper = InstahireScraper.__new__(InstahireScraper)
    
    # Basic search
    url = scraper.build_search_url(keyword="python developer")
    assert "instahyre.com" in url
    assert "q=python+developer" in url

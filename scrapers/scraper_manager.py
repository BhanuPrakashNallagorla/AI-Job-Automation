"""
Scraper Manager - Serper API Only.
Uses REAL job data from Google Jobs via Serper.dev
NO MOCK DATA - requires SERPER_API_KEY
"""
import logging
import os
from typing import List, Dict, Optional

from scrapers.serper_scraper import SerperJobScraper

logger = logging.getLogger(__name__)


class ScraperManager:
    """
    Manages job scraping using Serper API (REAL data only).
    Requires SERPER_API_KEY to function.
    """
    
    def __init__(self, serper_key: Optional[str] = None, **kwargs):
        """Initialize with Serper API key."""
        api_key = serper_key or os.getenv('SERPER_API_KEY')
        
        if not api_key:
            error_msg = (
                "❌ SERPER_API_KEY not found. "
                "Get your FREE API key at https://serper.dev/ (2,500 searches/month) "
                "and add it to your .env file."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.scraper = SerperJobScraper(api_key)
        logger.info("✅ ScraperManager initialized with Serper API")
    
    async def scrape_jobs(
        self, 
        keyword: str, 
        location: Optional[str] = None, 
        num_results: int = 50,
        **kwargs
    ) -> List[Dict]:
        """
        Scrape REAL jobs from Google Jobs.
        
        Args:
            keyword: Job search term
            location: Location filter
            num_results: Number of results
            
        Returns:
            List of real job dictionaries
        """
        logger.info(f"🔍 Scraping: {keyword} in {location}")
        
        # Serper scraper is synchronous, call directly
        jobs = self.scraper.scrape_jobs(
            keyword=keyword,
            location=location,
            num_results=num_results
        )
        
        # Add scraper info to each job
        for job in jobs:
            job['scraper_used'] = 'serper'
        
        logger.info(f"✅ Scraped {len(jobs)} real jobs")
        return jobs
    
    def get_status(self) -> Dict:
        """Get scraper status."""
        return {
            'serper': {
                'configured': True,
                'type': 'SerperJobScraper',
                'ready': True
            }
        }
    
    def test_scraper(self) -> Dict:
        """Test if scraper is working."""
        return self.scraper.test_connection()


# Test
if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print("TESTING SCRAPER MANAGER")
    print("="*60)
    
    try:
        manager = ScraperManager()
        
        # Test connection
        result = manager.test_scraper()
        if result['success']:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
            exit(1)
        
        # Test async scraping
        print("\n🔍 Testing async scrape...")
        jobs = asyncio.run(manager.scrape_jobs("Python Developer", "Bangalore", 5))
        print(f"✅ Found {len(jobs)} jobs")
        
        if jobs:
            print(f"\n📋 First job: {jobs[0]['job_title']} at {jobs[0]['company']}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTo fix: Add SERPER_API_KEY to .env file")
        print("Get free key at: https://serper.dev/")

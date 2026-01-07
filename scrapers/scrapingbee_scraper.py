"""
ScrapingBee Naukri Scraper.
Uses ScrapingBee proxy to bypass anti-bot protection.
FREE tier: 1,000 API credits
Get API key at: https://www.scrapingbee.com/
"""
import requests
from bs4 import BeautifulSoup
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ScrapingBeeNaukriScraper:
    """
    Scrapes Naukri using ScrapingBee proxy to bypass blocking.
    FREE tier: 1,000 API credits.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://app.scrapingbee.com/api/v1/"
    
    async def scrape_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        num_pages: int = 3,
        **kwargs
    ) -> List[Dict]:
        """
        Scrape Naukri using ScrapingBee.
        
        Args:
            keyword: Job search keyword
            location: Location filter
            num_pages: Number of pages to scrape
            
        Returns:
            List of job dictionaries
        """
        logger.info(f"Scraping Naukri via ScrapingBee: {keyword} in {location}")
        
        jobs = []
        
        try:
            for page in range(1, num_pages + 1):
                # Construct Naukri URL
                search_keyword = keyword.lower().replace(' ', '-')
                
                if location:
                    search_location = location.lower().replace(' ', '-').replace(',', '')
                    naukri_url = f"https://www.naukri.com/{search_keyword}-jobs-in-{search_location}"
                else:
                    naukri_url = f"https://www.naukri.com/{search_keyword}-jobs"
                
                if page > 1:
                    naukri_url += f"-{page}"
                
                logger.info(f"Scraping page {page}: {naukri_url}")
                
                # Request through ScrapingBee
                params = {
                    'api_key': self.api_key,
                    'url': naukri_url,
                    'render_js': 'true',  # Enable JS rendering for dynamic content
                    'premium_proxy': 'true',  # Use premium proxy for better success
                    'country_code': 'in',  # India proxy
                }
                
                response = requests.get(self.base_url, params=params, timeout=120)
                
                if response.status_code != 200:
                    logger.error(f"ScrapingBee error: {response.status_code}")
                    if page == 1:
                        raise Exception(f"ScrapingBee failed: {response.status_code}")
                    continue
                
                # Parse HTML
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Check for blocking
                page_text = soup.get_text().lower()
                if 'access denied' in page_text or 'blocked' in page_text:
                    logger.error("Page is blocked even with ScrapingBee")
                    raise Exception("Naukri blocked the request")
                
                # Find job cards - Naukri uses various class names
                job_cards = soup.find_all('article', class_=re.compile(r'jobTuple|job-tuple'))
                if not job_cards:
                    job_cards = soup.find_all('div', class_=re.compile(r'srp-jobtuple|cust-job-tuple'))
                if not job_cards:
                    job_cards = soup.find_all('div', {'data-job-id': True})
                
                logger.info(f"Found {len(job_cards)} jobs on page {page}")
                
                for card in job_cards:
                    try:
                        job = self._parse_job_card(card, location or "India")
                        if job and job.get('job_title') != 'Unknown':
                            jobs.append(job)
                    except Exception as e:
                        logger.warning(f"Error parsing job card: {e}")
                        continue
            
            logger.info(f"✅ Total scraped: {len(jobs)} jobs")
            return jobs
            
        except Exception as e:
            logger.error(f"Error scraping via ScrapingBee: {e}")
            raise
    
    def _parse_job_card(self, card, location: str) -> Dict:
        """Parse individual job card."""
        
        # Extract title
        title = "Unknown"
        title_elem = card.find('a', class_=re.compile(r'title|job-title|jobTitle'))
        if not title_elem:
            title_elem = card.find('a', {'class': lambda x: x and 'title' in str(x).lower()})
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # Extract job URL
        job_url = ""
        if title_elem and title_elem.get('href'):
            job_url = title_elem.get('href')
            if job_url.startswith('/'):
                job_url = f"https://www.naukri.com{job_url}"
        
        # Extract company
        company = "Unknown"
        company_elem = card.find(['a', 'span'], class_=re.compile(r'comp-name|company|companyInfo'))
        if company_elem:
            company = company_elem.get_text(strip=True)
        
        # Extract experience
        experience = None
        exp_elem = card.find(['span', 'li'], class_=re.compile(r'exp|experience'))
        if exp_elem:
            experience = exp_elem.get_text(strip=True)
        
        # Extract salary
        salary_min = None
        salary_max = None
        salary_elem = card.find(['span', 'li'], class_=re.compile(r'sal|salary'))
        if salary_elem:
            salary_text = salary_elem.get_text(strip=True)
            # Parse salary range (e.g., "10-15 Lacs")
            numbers = re.findall(r'[\d.]+', salary_text)
            if len(numbers) >= 2:
                try:
                    salary_min = int(float(numbers[0]) * 100000)
                    salary_max = int(float(numbers[1]) * 100000)
                except:
                    pass
        
        # Extract location
        job_location = location
        loc_elem = card.find(['span', 'li'], class_=re.compile(r'loc|location'))
        if loc_elem:
            job_location = loc_elem.get_text(strip=True)
        
        # Extract description/skills
        description = ""
        desc_elem = card.find(['div', 'span'], class_=re.compile(r'job-desc|ellipsis'))
        if desc_elem:
            description = desc_elem.get_text(strip=True)
        
        # Extract skills
        skills = []
        skills_elem = card.find(['ul', 'div'], class_=re.compile(r'tag|skill'))
        if skills_elem:
            skill_tags = skills_elem.find_all(['li', 'span', 'a'])
            skills = [s.get_text(strip=True) for s in skill_tags if s.get_text(strip=True)]
        
        job = {
            'job_title': title,
            'company': company,
            'location': job_location,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'experience_required': experience,
            'description': description,
            'description_snippet': description[:500] if description else '',
            'job_url': job_url,
            'source': 'naukri',
            'is_remote': 'remote' in title.lower() or 'remote' in job_location.lower(),
            'is_easy_apply': False,
            'skills': skills[:10],  # Limit skills
            'scraped_at': datetime.now().isoformat(),
        }
        
        return job


# Test script
if __name__ == "__main__":
    import asyncio
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    api_key = os.getenv('SCRAPINGBEE_API_KEY')
    if not api_key:
        print("❌ Please set SCRAPINGBEE_API_KEY environment variable")
        print("Get free API key from: https://www.scrapingbee.com/")
        exit(1)
    
    scraper = ScrapingBeeNaukriScraper(api_key=api_key)
    
    print("\n🔍 Testing Naukri scraping via ScrapingBee...")
    jobs = asyncio.run(scraper.scrape_jobs(
        keyword="Python Developer",
        location="Bangalore",
        num_pages=1
    ))
    
    print(f"\n✅ Found {len(jobs)} jobs")
    if jobs:
        print("\n📋 Sample job:")
        import json
        print(json.dumps(jobs[0], indent=2, default=str))

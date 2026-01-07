"""
JSearch API Scraper (RapidAPI).
FREE tier: 150 requests/month
Get API key at: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
"""
import requests
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class JSearchScraper:
    """
    Scrapes jobs using JSearch API (RapidAPI).
    FREE tier: 150 requests/month.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://jsearch.p.rapidapi.com/search"
        
    async def scrape_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        num_results: int = 50,
        **kwargs
    ) -> List[Dict]:
        """
        Scrape jobs using JSearch API.
        
        Args:
            keyword: Job search keyword
            location: Location filter
            num_results: Number of results to fetch
            
        Returns:
            List of job dictionaries
        """
        logger.info(f"Scraping jobs via JSearch API: {keyword} in {location}")
        
        try:
            # Construct query
            query = keyword
            if location:
                query += f" in {location}"
            
            # Calculate pages needed
            num_pages = max(1, (num_results + 9) // 10)  # 10 results per page
            
            querystring = {
                "query": query,
                "page": "1",
                "num_pages": str(min(num_pages, 5)),  # Max 5 pages
                "date_posted": "all"
            }
            
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            
            logger.info("Sending request to JSearch API...")
            response = requests.get(
                self.base_url, 
                headers=headers, 
                params=querystring, 
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"JSearch API error: {response.status_code} - {response.text}")
                raise Exception(f"API returned status {response.status_code}")
            
            data = response.json()
            
            # Parse jobs
            jobs = []
            if 'data' in data:
                for job_data in data['data'][:num_results]:
                    job = self._parse_job(job_data, location or "")
                    jobs.append(job)
                
                logger.info(f"✅ Scraped {len(jobs)} jobs from JSearch API")
            else:
                logger.warning("No jobs found in API response")
            
            return jobs
            
        except requests.exceptions.Timeout:
            logger.error("JSearch API request timed out")
            raise Exception("API request timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Failed to connect to JSearch API: {str(e)}")
        except Exception as e:
            logger.error(f"Error scraping via JSearch: {e}")
            raise
    
    def _parse_job(self, job_data: Dict, location: str) -> Dict:
        """Parse job data from JSearch response."""
        
        # Extract salary
        salary_min = None
        salary_max = None
        
        min_sal = job_data.get('job_min_salary')
        max_sal = job_data.get('job_max_salary')
        currency = job_data.get('job_salary_currency', '')
        
        if min_sal:
            salary_min = int(min_sal)
        if max_sal:
            salary_max = int(max_sal)
        
        # Extract experience from description
        experience = None
        description = job_data.get('job_description', '')
        if description:
            desc_lower = description.lower()
            if 'year' in desc_lower and 'experience' in desc_lower:
                match = re.search(r'(\d+)[\s\-to]+(\d+)?\s*(?:\+)?\s*year', desc_lower)
                if match:
                    if match.group(2):
                        experience = f"{match.group(1)}-{match.group(2)} years"
                    else:
                        experience = f"{match.group(1)}+ years"
        
        # Extract skills from highlights
        skills = []
        highlights = job_data.get('job_highlights', {})
        if isinstance(highlights, dict):
            qualifications = highlights.get('Qualifications', [])
            if isinstance(qualifications, list):
                for qual in qualifications[:5]:  # Take first 5
                    if len(qual) < 50:  # Short items are likely skills
                        skills.append(qual)
        
        # Build job dictionary
        job = {
            'job_title': job_data.get('job_title', 'Unknown'),
            'company': job_data.get('employer_name', 'Unknown'),
            'location': job_data.get('job_city', '') or job_data.get('job_country', location),
            'salary_min': salary_min,
            'salary_max': salary_max,
            'experience_required': experience,
            'description': description,
            'description_snippet': description[:500] if description else '',
            'job_url': job_data.get('job_apply_link') or job_data.get('job_google_link', ''),
            'source': 'jsearch',
            'posted_date': job_data.get('job_posted_at_datetime_utc'),
            'is_remote': job_data.get('job_is_remote', False),
            'is_easy_apply': 'apply' in job_data.get('job_apply_link', '').lower(),
            'skills': skills,
            'employment_type': job_data.get('job_employment_type', 'Full-time'),
            'scraped_at': datetime.now().isoformat(),
        }
        
        return job


# Test script
if __name__ == "__main__":
    import asyncio
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    api_key = os.getenv('RAPIDAPI_KEY')
    if not api_key:
        print("❌ Please set RAPIDAPI_KEY environment variable")
        print("Get free API key from: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch")
        exit(1)
    
    scraper = JSearchScraper(api_key=api_key)
    
    print("\n🔍 Testing job scraping...")
    jobs = asyncio.run(scraper.scrape_jobs(
        keyword="Python Developer",
        location="Bangalore, India",
        num_results=10
    ))
    
    print(f"\n✅ Found {len(jobs)} jobs")
    if jobs:
        print("\n📋 Sample job:")
        import json
        print(json.dumps(jobs[0], indent=2, default=str))

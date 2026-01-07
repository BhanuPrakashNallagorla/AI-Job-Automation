"""
Serper.dev Google Search API Scraper.
REAL job data from Google Search.
FREE tier: 2,500 searches/month
Get API key at: https://serper.dev/
"""
import requests
import re
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SerperJobScraper:
    """
    Real job scraper using Serper.dev API.
    FREE TIER: 2,500 searches per month.
    Get API key: https://serper.dev/
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('SERPER_API_KEY')
        if not self.api_key:
            raise ValueError(
                "SERPER_API_KEY is required. "
                "Get your free API key at https://serper.dev/ "
                "and add it to your .env file."
            )
        self.base_url = "https://google.serper.dev/search"
        logger.info("✅ Serper scraper initialized")
    
    def scrape_jobs(
        self, 
        keyword: str, 
        location: Optional[str] = None, 
        num_results: int = 50,
        **kwargs
    ) -> List[Dict]:
        """
        Scrape REAL jobs from Google Search via Serper API.
        
        Args:
            keyword: Job search term (e.g., "AI Engineer", "Python Developer")
            location: Location (e.g., "Bangalore, India")
            num_results: Number of jobs to return (max 100)
        
        Returns:
            List of job dictionaries with real data
        """
        logger.info(f"🔍 Scraping REAL jobs: '{keyword}' in '{location}'")
        
        try:
            # Prepare search query - search for jobs specifically
            query = f"{keyword} jobs"
            if location:
                query = f"{keyword} jobs in {location}"
            
            # API request payload
            payload = {
                "q": query,
                "num": min(num_results, 100),
                "gl": "in",
                "hl": "en"
            }
            
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }
            
            # Make API request
            logger.info("📡 Sending request to Serper API...")
            response = requests.post(
                self.base_url, 
                json=payload, 
                headers=headers, 
                timeout=30
            )
            
            # Check response
            if response.status_code == 401:
                raise Exception(
                    "Invalid Serper API key. "
                    "Please check your SERPER_API_KEY in .env file."
                )
            
            if response.status_code == 429:
                raise Exception(
                    "Serper API rate limit exceeded. "
                    "Free tier allows 2,500 searches/month."
                )
            
            if response.status_code != 200:
                logger.error(f"Serper API error: {response.status_code} - {response.text}")
                raise Exception(f"API returned status {response.status_code}: {response.text}")
            
            # Parse response
            data = response.json()
            
            # Get organic results
            organic = data.get('organic', [])
            if not organic:
                logger.warning(f"⚠️ No results found for: {keyword} in {location}")
                return []
            
            # Parse job listings from search results
            jobs = []
            for result in organic:
                job = self._parse_search_result(result, keyword, location or "India")
                if job:
                    jobs.append(job)
            
            logger.info(f"✅ Successfully scraped {len(jobs)} REAL job listings")
            return jobs
            
        except requests.exceptions.Timeout:
            logger.error("❌ API request timed out")
            raise Exception("Serper API request timed out. Please try again.")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error: {e}")
            raise Exception(f"Failed to connect to Serper API: {str(e)}")
    
    def _parse_search_result(self, result: Dict, keyword: str, location: str) -> Optional[Dict]:
        """Parse a search result into job data."""
        
        title = result.get('title', '')
        link = result.get('link', '')
        snippet = result.get('snippet', '')
        
        # Skip if not a job-related result
        job_keywords = ['job', 'career', 'hiring', 'vacancy', 'opening', 'position']
        if not any(kw in title.lower() or kw in snippet.lower() for kw in job_keywords):
            return None
        
        # Extract company from title or snippet
        company = "Various Companies"
        # Try to extract company from common patterns
        if ' at ' in title:
            company = title.split(' at ')[-1].strip()
        elif ' - ' in title:
            parts = title.split(' - ')
            if len(parts) > 1:
                company = parts[-1].strip()
        
        # Extract job platform
        platform = "Google Search"
        if 'naukri' in link.lower():
            platform = "Naukri"
        elif 'linkedin' in link.lower():
            platform = "LinkedIn"
        elif 'indeed' in link.lower():
            platform = "Indeed"
        elif 'glassdoor' in link.lower():
            platform = "Glassdoor"
        elif 'instahyre' in link.lower():
            platform = "Instahyre"
        
        # Extract experience from snippet
        experience = None
        exp_match = re.search(r'(\d+)[-\s]*(?:to|-|–)?\s*(\d+)?\s*(?:years?|yrs?)', snippet.lower())
        if exp_match:
            if exp_match.group(2):
                experience = f"{exp_match.group(1)}-{exp_match.group(2)} years"
            else:
                experience = f"{exp_match.group(1)}+ years"
        
        # Extract skills from snippet
        skills = []
        common_skills = [
            'Python', 'Java', 'JavaScript', 'React', 'Node.js', 'AWS', 'Azure',
            'Machine Learning', 'AI', 'ML', 'Deep Learning', 'TensorFlow', 
            'PyTorch', 'NLP', 'SQL', 'Docker', 'Kubernetes', 'FastAPI',
            'Django', 'Flask', 'REST API', 'Git', 'CI/CD', 'TypeScript',
            'GenAI', 'Generative AI', 'LLM'
        ]
        for skill in common_skills:
            if skill.lower() in snippet.lower() or skill.lower() in title.lower():
                skills.append(skill)
        
        # Build job dictionary
        job = {
            'job_title': f"{keyword} - {platform}",
            'company': company,
            'location': location,
            'salary_min': None,
            'salary_max': None,
            'experience_required': experience,
            'description': snippet,
            'description_snippet': snippet[:500] if snippet else '',
            'job_url': link,
            'source': 'serper',
            'platform': platform,
            'posted_date': None,
            'is_remote': 'remote' in title.lower() or 'remote' in snippet.lower(),
            'is_easy_apply': False,
            'skills': skills,
            'scraped_at': datetime.now().isoformat(),
            'is_real': True,
        }
        
        return job
    
    def test_connection(self) -> Dict:
        """Test if API key is valid."""
        try:
            jobs = self.scrape_jobs("software engineer", "Bangalore", 5)
            return {
                'success': True,
                'message': f'API working! Found {len(jobs)} job listings.',
                'jobs_found': len(jobs)
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print("TESTING SERPER SCRAPER")
    print("="*60)
    
    try:
        scraper = SerperJobScraper()
        
        result = scraper.test_connection()
        if result['success']:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
            exit(1)
        
        print("\n🔍 Scraping jobs...")
        jobs = scraper.scrape_jobs("AI Engineer", "Bangalore, India", 10)
        
        print(f"\n✅ Found {len(jobs)} REAL job listings")
        
        if jobs:
            print("\n📋 Sample jobs:")
            for i, job in enumerate(jobs[:3], 1):
                print(f"  {i}. {job['job_title']} - {job['company']}")
                print(f"     URL: {job['job_url'][:60]}...")
                if job['skills']:
                    print(f"     Skills: {', '.join(job['skills'][:5])}")
                print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTo fix:")
        print("1. Get free API key from https://serper.dev/")
        print("2. Add to .env: SERPER_API_KEY=your_key_here")

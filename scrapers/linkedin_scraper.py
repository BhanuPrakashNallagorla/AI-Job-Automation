"""
LinkedIn Job Scraper.
Handles LinkedIn's authentication and anti-scraping measures.
"""
import re
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode, quote
import structlog

from scrapers.base_scraper import BaseScraper, ScrapingError, BlockedError
from config import settings


logger = structlog.get_logger(__name__)


class LinkedInScraper(BaseScraper):
    """
    LinkedIn job scraper with authentication support.
    
    Note: LinkedIn has strict anti-scraping measures. This scraper:
    - Uses session cookies for authentication
    - Implements careful rate limiting
    - Detects Easy Apply jobs
    - Respects LinkedIn's terms of service
    
    For production use, consider using LinkedIn's official API.
    """
    
    BASE_URL = "https://www.linkedin.com"
    JOBS_URL = "https://www.linkedin.com/jobs/search"
    
    # Selectors
    SELECTORS = {
        "job_card": ".jobs-search-results__list-item, .job-card-container",
        "job_title": ".job-card-list__title, .job-card-container__link",
        "company_name": ".job-card-container__primary-description, .job-card-container__company-name",
        "location": ".job-card-container__metadata-item, .job-card-container__metadata-wrapper",
        "posted_date": ".job-card-container__footer-item time",
        "easy_apply": ".job-card-container__apply-method, [data-test-job-apply-method]",
        "job_url": ".job-card-list__title a, .job-card-container__link",
        "description": ".jobs-description-content__text",
        "next_page": "button[aria-label='Next']",
        "pagination": ".jobs-search-results-list__pagination",
        "login_form": "#session_key",
        "auth_wall": ".authwall",
    }
    
    # Experience level mapping
    EXPERIENCE_MAP = {
        "fresher": "1",      # Internship
        "entry": "2",        # Entry level
        "associate": "3",    # Associate
        "mid-senior": "4",   # Mid-Senior level
        "director": "5",     # Director
        "executive": "6",    # Executive
    }
    
    @property
    def platform_name(self) -> str:
        return "linkedin"
    
    def __init__(
        self,
        session_cookie: Optional[str] = None,
        headless: bool = True,
        **kwargs
    ):
        """
        Initialize LinkedIn scraper.
        
        Args:
            session_cookie: LinkedIn li_at session cookie for authentication
            headless: Run browser in headless mode
        """
        super().__init__(headless=headless, **kwargs)
        self.session_cookie = session_cookie or settings.linkedin_session_cookie
        self._is_authenticated = False
    
    async def authenticate(self) -> bool:
        """
        Authenticate with LinkedIn using session cookie.
        
        Returns:
            True if authentication successful
        """
        if not self.session_cookie:
            self.logger.warning("No LinkedIn session cookie provided")
            return False
        
        try:
            # Add session cookie
            await self._context.add_cookies([{
                "name": "li_at",
                "value": self.session_cookie,
                "domain": ".linkedin.com",
                "path": "/",
            }])
            
            # Verify authentication
            await self._page.goto(f"{self.BASE_URL}/feed/", wait_until="domcontentloaded")
            await self._page.wait_for_timeout(2000)
            
            # Check if we're on the feed (authenticated) or login page
            current_url = self._page.url
            if "login" in current_url or "authwall" in current_url:
                self.logger.error("LinkedIn authentication failed")
                return False
            
            self._is_authenticated = True
            self.logger.info("LinkedIn authentication successful")
            return True
            
        except Exception as e:
            self.logger.error("LinkedIn authentication error", error=str(e))
            return False
    
    def build_search_url(
        self,
        keyword: str,
        location: Optional[str] = None,
        experience_level: Optional[str] = None,
        job_type: Optional[str] = None,
        remote: bool = False,
        page: int = 1,
        **kwargs
    ) -> str:
        """
        Build LinkedIn job search URL.
        
        Args:
            keyword: Job search keyword
            location: Location filter
            experience_level: Experience level filter
            job_type: Job type (full-time, part-time, contract)
            remote: Filter for remote jobs
            page: Page number
        """
        params = {
            "keywords": keyword,
            "refresh": "true",
        }
        
        if location:
            params["location"] = location
        
        if experience_level:
            exp_code = self.EXPERIENCE_MAP.get(experience_level.lower())
            if exp_code:
                params["f_E"] = exp_code
        
        # Job type
        job_type_map = {
            "full-time": "F",
            "part-time": "P",
            "contract": "C",
            "temporary": "T",
            "internship": "I",
        }
        if job_type and job_type.lower() in job_type_map:
            params["f_JT"] = job_type_map[job_type.lower()]
        
        # Remote filter
        if remote:
            params["f_WT"] = "2"  # Remote
        
        # Pagination (LinkedIn uses start parameter)
        if page > 1:
            params["start"] = str((page - 1) * 25)  # 25 jobs per page
        
        return f"{self.JOBS_URL}?{urlencode(params)}"
    
    async def init_browser(self) -> None:
        """Initialize browser and authenticate if cookie provided."""
        await super().init_browser()
        
        if self.session_cookie:
            await self.authenticate()
    
    async def get_job_cards(self) -> List:
        """Get job card elements from current page."""
        try:
            # Wait for job cards to load
            await self._page.wait_for_selector(
                self.SELECTORS["job_card"],
                timeout=10000
            )
            
            # Scroll to load all jobs
            await self._scroll_job_list()
            
            return await self._page.query_selector_all(self.SELECTORS["job_card"])
            
        except Exception as e:
            self.logger.warning("Failed to get LinkedIn job cards", error=str(e))
            
            # Check for auth wall
            if await self._check_auth_wall():
                raise BlockedError("LinkedIn requires authentication")
            
            return []
    
    async def _scroll_job_list(self) -> None:
        """Scroll the job list to load all lazy-loaded items."""
        try:
            jobs_list = await self._page.query_selector(".jobs-search-results-list")
            if not jobs_list:
                return
            
            for _ in range(5):
                await jobs_list.evaluate(
                    "el => el.scrollTop = el.scrollHeight"
                )
                await self._page.wait_for_timeout(1000)
                
        except Exception:
            pass
    
    async def _check_auth_wall(self) -> bool:
        """Check if we hit LinkedIn's auth wall."""
        auth_wall = await self._page.query_selector(self.SELECTORS["auth_wall"])
        login_form = await self._page.query_selector(self.SELECTORS["login_form"])
        return bool(auth_wall or login_form)
    
    async def parse_job_card(self, job_element) -> Optional[Dict[str, Any]]:
        """Parse a LinkedIn job card into structured data."""
        try:
            job_data = {}
            
            # Job Title
            title_el = await job_element.query_selector(self.SELECTORS["job_title"])
            if title_el:
                job_data["job_title"] = self.clean_text(await title_el.inner_text())
                
                # Get job URL
                href = await title_el.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        job_data["job_url"] = f"{self.BASE_URL}{href}"
                    else:
                        job_data["job_url"] = href
            
            if not job_data.get("job_title"):
                return None
            
            # Company Name
            company_el = await job_element.query_selector(self.SELECTORS["company_name"])
            if company_el:
                job_data["company"] = self.clean_text(await company_el.inner_text())
            
            # Location
            loc_el = await job_element.query_selector(self.SELECTORS["location"])
            if loc_el:
                location_text = self.clean_text(await loc_el.inner_text())
                # LinkedIn location often includes job type, clean it
                job_data["location"] = location_text.split("·")[0].strip()
            
            # Posted Date
            date_el = await job_element.query_selector(self.SELECTORS["posted_date"])
            if date_el:
                date_text = await date_el.get_attribute("datetime")
                if date_text:
                    job_data["posted_date"] = date_text
                else:
                    job_data["posted_date_text"] = await date_el.inner_text()
            
            # Easy Apply Detection
            easy_apply_el = await job_element.query_selector(self.SELECTORS["easy_apply"])
            if easy_apply_el:
                apply_text = await easy_apply_el.inner_text()
                job_data["is_easy_apply"] = "easy apply" in apply_text.lower()
            else:
                job_data["is_easy_apply"] = False
            
            # Extract job ID from URL
            if job_data.get("job_url"):
                job_id_match = re.search(r"/jobs/view/(\d+)", job_data["job_url"])
                if job_id_match:
                    job_data["linkedin_job_id"] = job_id_match.group(1)
            
            return job_data
            
        except Exception as e:
            self.logger.warning("Failed to parse LinkedIn job card", error=str(e))
            return None
    
    async def has_next_page(self) -> bool:
        """Check if there's a next page."""
        try:
            next_btn = await self._page.query_selector(self.SELECTORS["next_page"])
            if next_btn:
                is_disabled = await next_btn.get_attribute("disabled")
                return not is_disabled
            return False
        except Exception:
            return False
    
    async def go_to_next_page(self) -> bool:
        """Navigate to next page."""
        try:
            next_btn = await self._page.query_selector(self.SELECTORS["next_page"])
            if next_btn:
                await next_btn.click()
                await self._page.wait_for_load_state("domcontentloaded")
                await self.random_delay()
                return True
            return False
        except Exception as e:
            self.logger.error("Failed to go to next page", error=str(e))
            return False
    
    async def get_job_details(self, job_url: str) -> Optional[Dict[str, Any]]:
        """Get full job details from job page."""
        try:
            await self.navigate_with_retry(job_url)
            
            details = {}
            
            # Full description
            desc_el = await self._page.query_selector(self.SELECTORS["description"])
            if desc_el:
                details["full_description"] = await desc_el.inner_text()
            
            # Skills from job page
            skills_section = await self._page.query_selector(
                ".job-details-skill-match-status-list"
            )
            if skills_section:
                skill_items = await skills_section.query_selector_all("li")
                details["skills"] = [
                    self.clean_text(await s.inner_text())
                    for s in skill_items
                ]
            
            return details
            
        except Exception as e:
            self.logger.warning("Failed to get LinkedIn job details", error=str(e))
            return None


# ============================================================================
# Convenience Function
# ============================================================================

async def scrape_linkedin_jobs(
    keyword: str,
    location: Optional[str] = None,
    session_cookie: Optional[str] = None,
    num_pages: int = 3,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Convenience function to scrape LinkedIn jobs.
    
    Note: Requires a valid session cookie for authenticated scraping.
    """
    scraper = LinkedInScraper(session_cookie=session_cookie)
    return await scraper.scrape_jobs(
        keyword=keyword,
        location=location,
        num_pages=num_pages,
        **kwargs
    )

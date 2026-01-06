"""
Naukri.com Job Scraper.
Production-ready scraper with anti-detection measures and robust error handling.
"""
import re
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode, quote
import structlog

from scrapers.base_scraper import BaseScraper, ScrapingError


logger = structlog.get_logger(__name__)


class NaukriScraper(BaseScraper):
    """
    Production-ready Naukri.com job scraper.
    
    Features:
    - Dynamic content loading handling
    - Anti-bot detection measures
    - Comprehensive field extraction
    - Pagination support
    - Error recovery and checkpointing
    """
    
    BASE_URL = "https://www.naukri.com"
    SEARCH_URL = "https://www.naukri.com/jobs-in-india"
    
    # Selectors for job elements
    SELECTORS = {
        "job_card": "article.jobTuple",
        "job_card_alt": ".cust-job-tuple",
        "job_card_new": "[data-job-id]",
        "job_title": ".title, .jobTitle a, .info h2 a",
        "company_name": ".comp-name, .companyInfo a, .info .company-name",
        "location": ".loc, .location, .locWdth",
        "experience": ".exp, .experience",
        "salary": ".sal, .salary",
        "skills": ".tags li, .skills-container span",
        "description": ".job-desc, .job-description",
        "posted_date": ".date, .posted-date, .job-post-day",
        "job_url": "a.title, .info h2 a, [href*='/job-listings']",
        "pagination": ".pagination",
        "next_page": ".pagination a:has-text('Next'), .fright a",
        "total_jobs": ".count-string, .total-count",
        "no_results": ".no-result, .noResultFound",
    }
    
    # Experience level mapping
    EXPERIENCE_LEVELS = {
        "fresher": "0",
        "0-1": "0to1",
        "1-3": "1to5",
        "3-5": "3to6",
        "5-10": "5to10",
        "10+": "10to15",
    }
    
    @property
    def platform_name(self) -> str:
        return "naukri"
    
    def build_search_url(
        self,
        keyword: str,
        location: Optional[str] = None,
        experience_level: Optional[str] = None,
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
        page: int = 1,
        **kwargs
    ) -> str:
        """
        Build Naukri search URL with filters.
        
        Args:
            keyword: Job search keyword
            location: City or location filter
            experience_level: Experience range (e.g., "0-1", "3-5", "fresher")
            salary_min: Minimum salary in LPA
            salary_max: Maximum salary in LPA
            page: Page number (1-indexed)
            **kwargs: Additional filters (work_from_home, company_type, etc.)
        """
        # Format keyword for URL
        keyword_slug = keyword.lower().replace(" ", "-").replace("_", "-")
        keyword_slug = re.sub(r"[^a-z0-9-]", "", keyword_slug)
        
        # Build base URL
        if location:
            location_slug = location.lower().replace(" ", "-")
            url = f"{self.BASE_URL}/{keyword_slug}-jobs-in-{location_slug}"
        else:
            url = f"{self.BASE_URL}/{keyword_slug}-jobs"
        
        # Build query parameters
        params = {}
        
        # Experience filter
        if experience_level:
            exp_value = self.EXPERIENCE_LEVELS.get(experience_level.lower())
            if exp_value:
                params["experience"] = exp_value
        
        # Salary filter
        if salary_min:
            params["salaryMin"] = str(salary_min)
        if salary_max:
            params["salaryMax"] = str(salary_max)
        
        # Page number (Naukri uses 1-indexed pages)
        if page > 1:
            params["pageNo"] = str(page)
        
        # Additional filters from kwargs
        if kwargs.get("work_from_home"):
            params["wfhType"] = "1"
        
        if kwargs.get("posted_within"):
            # 1 = today, 3 = last 3 days, 7 = last week
            params["jdAgeInDays"] = str(kwargs["posted_within"])
        
        if kwargs.get("company_type"):
            params["compType"] = kwargs["company_type"]
        
        # Construct final URL
        if params:
            url = f"{url}?{urlencode(params)}"
        
        return url
    
    async def wait_for_job_cards(self, timeout: int = 15000) -> bool:
        """Wait for job cards to load on the page."""
        try:
            # Try multiple selectors
            for selector in [
                self.SELECTORS["job_card"],
                self.SELECTORS["job_card_alt"],
                self.SELECTORS["job_card_new"]
            ]:
                try:
                    await self._page.wait_for_selector(selector, timeout=timeout)
                    return True
                except Exception:
                    continue
            
            # Check for no results page
            no_results = await self._page.query_selector(self.SELECTORS["no_results"])
            if no_results:
                self.logger.info("No job results found")
                return False
            
            return False
            
        except Exception as e:
            self.logger.warning("Failed to wait for job cards", error=str(e))
            return False
    
    async def scroll_to_load_all(self) -> None:
        """Scroll page to load all lazy-loaded content."""
        try:
            # Get page height
            prev_height = await self._page.evaluate("document.body.scrollHeight")
            
            # Scroll down incrementally
            for _ in range(5):
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self._page.wait_for_timeout(1000)
                
                new_height = await self._page.evaluate("document.body.scrollHeight")
                if new_height == prev_height:
                    break
                prev_height = new_height
            
            # Scroll back to top
            await self._page.evaluate("window.scrollTo(0, 0)")
            await self._page.wait_for_timeout(500)
            
        except Exception as e:
            self.logger.warning("Scroll loading failed", error=str(e))
    
    async def get_job_cards(self) -> List:
        """Get all job card elements from current page."""
        await self.wait_for_job_cards()
        await self.scroll_to_load_all()
        
        # Try different selectors
        for selector in [
            self.SELECTORS["job_card"],
            self.SELECTORS["job_card_alt"],
            self.SELECTORS["job_card_new"]
        ]:
            cards = await self._page.query_selector_all(selector)
            if cards:
                self.logger.debug("Found job cards", selector=selector, count=len(cards))
                return cards
        
        self.logger.warning("No job cards found with any selector")
        return []
    
    async def parse_job_card(self, job_element) -> Optional[Dict[str, Any]]:
        """
        Parse a single job card element into structured data.
        
        Extracts:
        - job_title, company, location
        - salary (min/max), experience
        - description, skills, posted_date
        - job_url, is_easy_apply
        """
        try:
            job_data = {}
            
            # Job Title
            title_el = await job_element.query_selector(self.SELECTORS["job_title"])
            if title_el:
                job_data["job_title"] = self.clean_text(await title_el.inner_text())
            else:
                # Try getting from data attribute
                job_data["job_title"] = await job_element.get_attribute("data-title") or ""
            
            if not job_data.get("job_title"):
                return None  # Skip cards without title
            
            # Company Name
            company_el = await job_element.query_selector(self.SELECTORS["company_name"])
            if company_el:
                job_data["company"] = self.clean_text(await company_el.inner_text())
            else:
                job_data["company"] = await job_element.get_attribute("data-company-name") or "Unknown"
            
            # Location
            loc_el = await job_element.query_selector(self.SELECTORS["location"])
            if loc_el:
                job_data["location"] = self.clean_text(await loc_el.inner_text())
            
            # Experience
            exp_el = await job_element.query_selector(self.SELECTORS["experience"])
            if exp_el:
                exp_text = self.clean_text(await exp_el.inner_text())
                job_data["experience_required"] = exp_text
                exp_parsed = self.parse_experience(exp_text)
                job_data["experience_min"] = exp_parsed.get("min")
                job_data["experience_max"] = exp_parsed.get("max")
            
            # Salary
            salary_el = await job_element.query_selector(self.SELECTORS["salary"])
            if salary_el:
                salary_text = self.clean_text(await salary_el.inner_text())
                if salary_text and "not disclosed" not in salary_text.lower():
                    job_data["salary_text"] = salary_text
                    salary_parsed = self.parse_salary(salary_text)
                    job_data["salary_min"] = salary_parsed.get("min")
                    job_data["salary_max"] = salary_parsed.get("max")
            
            # Skills/Tags
            skill_elements = await job_element.query_selector_all(self.SELECTORS["skills"])
            skills = []
            for skill_el in skill_elements:
                skill_text = self.clean_text(await skill_el.inner_text())
                if skill_text and len(skill_text) < 50:
                    skills.append(skill_text)
            if skills:
                job_data["skills"] = skills
            
            # Description/Snippet
            desc_el = await job_element.query_selector(self.SELECTORS["description"])
            if desc_el:
                job_data["description_snippet"] = self.clean_text(await desc_el.inner_text())
            
            # Posted Date
            date_el = await job_element.query_selector(self.SELECTORS["posted_date"])
            if date_el:
                date_text = self.clean_text(await date_el.inner_text())
                job_data["posted_date_text"] = date_text
                job_data["posted_date"] = self._parse_posted_date(date_text)
            
            # Job URL
            url_el = await job_element.query_selector(self.SELECTORS["job_url"])
            if url_el:
                href = await url_el.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        job_data["job_url"] = f"{self.BASE_URL}{href}"
                    else:
                        job_data["job_url"] = href
            
            # If no URL found, try data attribute
            if not job_data.get("job_url"):
                job_id = await job_element.get_attribute("data-job-id")
                if job_id:
                    job_data["job_url"] = f"{self.BASE_URL}/job-listings-{job_id}"
            
            # Fallback for missing URL
            if not job_data.get("job_url"):
                # Generate a unique identifier
                import hashlib
                unique_str = f"{job_data.get('job_title', '')}{job_data.get('company', '')}"
                hash_id = hashlib.md5(unique_str.encode()).hexdigest()[:12]
                job_data["job_url"] = f"{self.BASE_URL}/job/{hash_id}"
            
            # Check for premium/featured
            job_data["is_premium"] = await job_element.get_attribute("data-premium") == "true"
            
            return job_data
            
        except Exception as e:
            self.logger.warning("Failed to parse job card", error=str(e))
            return None
    
    def _parse_posted_date(self, date_text: str) -> Optional[str]:
        """Parse posted date text to ISO format."""
        if not date_text:
            return None
        
        date_text = date_text.lower().strip()
        today = datetime.now()
        
        try:
            if "today" in date_text or "just now" in date_text:
                return today.isoformat()
            
            if "yesterday" in date_text:
                return (today - timedelta(days=1)).isoformat()
            
            # "X days ago" pattern
            days_match = re.search(r"(\d+)\s*days?\s*ago", date_text)
            if days_match:
                days = int(days_match.group(1))
                return (today - timedelta(days=days)).isoformat()
            
            # "X hours ago" pattern
            hours_match = re.search(r"(\d+)\s*hours?\s*ago", date_text)
            if hours_match:
                return today.isoformat()
            
            # "Few hours ago" or similar
            if "hour" in date_text:
                return today.isoformat()
            
            # Try to parse actual date
            for fmt in ["%d %b %Y", "%d-%m-%Y", "%Y-%m-%d"]:
                try:
                    parsed = datetime.strptime(date_text, fmt)
                    return parsed.isoformat()
                except ValueError:
                    continue
            
        except Exception:
            pass
        
        return None
    
    async def has_next_page(self) -> bool:
        """Check if there's a next page of results."""
        try:
            # Check for next button
            next_btn = await self._page.query_selector(self.SELECTORS["next_page"])
            if next_btn:
                is_disabled = await next_btn.get_attribute("disabled")
                if not is_disabled:
                    return True
            
            # Check pagination numbers
            current_url = self._page.url
            page_match = re.search(r"pageNo=(\d+)", current_url)
            current_page = int(page_match.group(1)) if page_match else 1
            
            # Check if there are more pages in pagination
            pagination = await self._page.query_selector(self.SELECTORS["pagination"])
            if pagination:
                last_page_link = await pagination.query_selector("a:last-child")
                if last_page_link:
                    href = await last_page_link.get_attribute("href")
                    if href:
                        last_match = re.search(r"pageNo=(\d+)", href)
                        if last_match:
                            last_page = int(last_match.group(1))
                            return current_page < last_page
            
            return False
            
        except Exception as e:
            self.logger.warning("Failed to check next page", error=str(e))
            return False
    
    async def go_to_next_page(self) -> bool:
        """Navigate to the next page of results."""
        try:
            # Try clicking next button
            next_btn = await self._page.query_selector(self.SELECTORS["next_page"])
            if next_btn:
                await next_btn.click()
                await self._page.wait_for_load_state("domcontentloaded")
                await self.random_delay()
                return True
            
            # Try modifying URL
            current_url = self._page.url
            page_match = re.search(r"pageNo=(\d+)", current_url)
            
            if page_match:
                current_page = int(page_match.group(1))
                next_url = current_url.replace(
                    f"pageNo={current_page}",
                    f"pageNo={current_page + 1}"
                )
            else:
                separator = "&" if "?" in current_url else "?"
                next_url = f"{current_url}{separator}pageNo=2"
            
            await self.navigate_with_retry(next_url)
            return True
            
        except Exception as e:
            self.logger.error("Failed to go to next page", error=str(e))
            return False
    
    async def get_job_details(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Get full job details from job page.
        
        Use this to get complete job description for JD analysis.
        """
        try:
            await self.navigate_with_retry(job_url)
            
            details = {}
            
            # Full description
            desc_selectors = [
                ".job-desc", 
                ".dang-inner-html",
                ".styles_JDC__dang-inner-html__h0K4t",
                "[class*='job-desc']",
                ".other-details"
            ]
            
            for selector in desc_selectors:
                desc_el = await self._page.query_selector(selector)
                if desc_el:
                    details["full_description"] = await desc_el.inner_text()
                    break
            
            # Key Skills
            skills_el = await self._page.query_selector(".key-skill")
            if skills_el:
                skill_items = await skills_el.query_selector_all("a, span")
                details["key_skills"] = [
                    self.clean_text(await s.inner_text()) 
                    for s in skill_items
                ]
            
            # Company details
            company_info = await self._page.query_selector(".company-info")
            if company_info:
                details["company_info"] = await company_info.inner_text()
            
            # Education requirements
            edu_el = await self._page.query_selector(".education")
            if edu_el:
                details["education"] = await edu_el.inner_text()
            
            return details
            
        except Exception as e:
            self.logger.warning("Failed to get job details", url=job_url, error=str(e))
            return None
    
    async def scrape_with_job_details(
        self,
        keyword: str,
        location: Optional[str] = None,
        num_pages: int = 5,
        fetch_details: bool = True,
        max_details: int = 50,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Scrape jobs with full details.
        
        If fetch_details is True, navigates to each job page to get
        full description (useful for JD analysis).
        
        Args:
            keyword: Search keyword
            location: Location filter
            num_pages: Pages to scrape
            fetch_details: Whether to fetch full job details
            max_details: Maximum jobs to fetch details for
            **kwargs: Additional search parameters
        """
        # First scrape the list
        jobs = await self.scrape_jobs(
            keyword=keyword,
            location=location,
            num_pages=num_pages,
            **kwargs
        )
        
        if not fetch_details or not jobs:
            return jobs
        
        # Fetch details for top jobs
        try:
            await self.init_browser()
            
            for i, job in enumerate(jobs[:max_details]):
                if not job.get("job_url"):
                    continue
                
                self.logger.info(
                    "Fetching job details",
                    progress=f"{i + 1}/{min(len(jobs), max_details)}",
                    title=job.get("job_title", "")[:50]
                )
                
                details = await self.get_job_details(job["job_url"])
                if details:
                    job.update(details)
                
                await self.random_delay(multiplier=0.5)
            
        except Exception as e:
            self.logger.error("Failed during detail fetching", error=str(e))
        
        finally:
            await self.close_browser()
        
        return jobs


# ============================================================================
# Convenience Functions
# ============================================================================

async def scrape_naukri_jobs(
    keyword: str,
    location: Optional[str] = None,
    experience_level: Optional[str] = None,
    num_pages: int = 5,
    headless: bool = True,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Convenience function to scrape Naukri jobs.
    
    Example:
        jobs = await scrape_naukri_jobs(
            keyword="python developer",
            location="bangalore",
            experience_level="3-5",
            num_pages=3
        )
    """
    scraper = NaukriScraper(headless=headless)
    return await scraper.scrape_jobs(
        keyword=keyword,
        location=location,
        experience_level=experience_level,
        num_pages=num_pages,
        **kwargs
    )

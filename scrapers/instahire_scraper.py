"""
Instahire Job Scraper.
Platform-specific implementation for Instahire job listings.
"""
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode
import structlog

from scrapers.base_scraper import BaseScraper


logger = structlog.get_logger(__name__)


class InstahireScraper(BaseScraper):
    """
    Instahire job platform scraper.
    
    Note: Instahire has different UI patterns. This scraper
    adapts the base scraper for Instahire-specific elements.
    """
    
    BASE_URL = "https://www.instahyre.com"
    SEARCH_URL = "https://www.instahyre.com/search-jobs"
    
    # Selectors (adjust based on actual Instahire DOM)
    SELECTORS = {
        "job_card": ".job-card, .job-listing-item, [data-job-id]",
        "job_title": ".job-title, .position-title, h3",
        "company_name": ".company-name, .employer-name",
        "location": ".location, .job-location",
        "salary": ".salary, .compensation",
        "experience": ".experience, .exp-required",
        "skills": ".skills span, .tags a",
        "posted_date": ".posted-date, .date",
        "job_url": ".job-title a, .view-job",
        "next_page": ".pagination .next, button[aria-label='Next']",
        "no_results": ".no-jobs-found, .empty-state",
    }
    
    @property
    def platform_name(self) -> str:
        return "instahire"
    
    def build_search_url(
        self,
        keyword: str,
        location: Optional[str] = None,
        experience_level: Optional[str] = None,
        page: int = 1,
        **kwargs
    ) -> str:
        """Build Instahire search URL."""
        params = {
            "q": keyword,
        }
        
        if location:
            params["location"] = location
        
        if experience_level:
            params["exp"] = experience_level
        
        if page > 1:
            params["page"] = str(page)
        
        return f"{self.SEARCH_URL}?{urlencode(params)}"
    
    async def get_job_cards(self) -> List:
        """Get job card elements from current page."""
        try:
            await self._page.wait_for_selector(
                self.SELECTORS["job_card"],
                timeout=10000
            )
            return await self._page.query_selector_all(self.SELECTORS["job_card"])
        except Exception as e:
            self.logger.warning("Failed to get Instahire job cards", error=str(e))
            return []
    
    async def parse_job_card(self, job_element) -> Optional[Dict[str, Any]]:
        """Parse Instahire job card."""
        try:
            job_data = {}
            
            # Job Title
            title_el = await job_element.query_selector(self.SELECTORS["job_title"])
            if title_el:
                job_data["job_title"] = self.clean_text(await title_el.inner_text())
            
            if not job_data.get("job_title"):
                return None
            
            # Company
            company_el = await job_element.query_selector(self.SELECTORS["company_name"])
            if company_el:
                job_data["company"] = self.clean_text(await company_el.inner_text())
            
            # Location
            loc_el = await job_element.query_selector(self.SELECTORS["location"])
            if loc_el:
                job_data["location"] = self.clean_text(await loc_el.inner_text())
            
            # Salary
            salary_el = await job_element.query_selector(self.SELECTORS["salary"])
            if salary_el:
                salary_text = self.clean_text(await salary_el.inner_text())
                job_data["salary_text"] = salary_text
                salary_parsed = self.parse_salary(salary_text)
                job_data["salary_min"] = salary_parsed.get("min")
                job_data["salary_max"] = salary_parsed.get("max")
            
            # Experience
            exp_el = await job_element.query_selector(self.SELECTORS["experience"])
            if exp_el:
                job_data["experience_required"] = self.clean_text(await exp_el.inner_text())
            
            # Skills
            skill_elements = await job_element.query_selector_all(self.SELECTORS["skills"])
            skills = []
            for skill_el in skill_elements:
                skill = self.clean_text(await skill_el.inner_text())
                if skill:
                    skills.append(skill)
            if skills:
                job_data["skills"] = skills
            
            # Job URL
            url_el = await job_element.query_selector(self.SELECTORS["job_url"])
            if url_el:
                href = await url_el.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        job_data["job_url"] = f"{self.BASE_URL}{href}"
                    else:
                        job_data["job_url"] = href
            
            # Posted date
            date_el = await job_element.query_selector(self.SELECTORS["posted_date"])
            if date_el:
                job_data["posted_date_text"] = self.clean_text(await date_el.inner_text())
            
            return job_data
            
        except Exception as e:
            self.logger.warning("Failed to parse Instahire job card", error=str(e))
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
            self.logger.error("Failed to navigate to next page", error=str(e))
            return False


# ============================================================================
# Convenience Function
# ============================================================================

async def scrape_instahire_jobs(
    keyword: str,
    location: Optional[str] = None,
    num_pages: int = 3,
    **kwargs
) -> List[Dict[str, Any]]:
    """Convenience function to scrape Instahire jobs."""
    scraper = InstahireScraper()
    return await scraper.scrape_jobs(
        keyword=keyword,
        location=location,
        num_pages=num_pages,
        **kwargs
    )

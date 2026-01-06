"""
Base Scraper Abstract Class.
Provides common functionality for all job scrapers with:
- Rate limiting and exponential backoff
- User agent rotation
- Proxy support
- Error handling and retry logic
- Progress saving for resumable scraping
"""
import json
import random
import asyncio
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import structlog

from fake_useragent import UserAgent
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import settings


logger = structlog.get_logger(__name__)


class ScrapingError(Exception):
    """Base exception for scraping errors."""
    pass


class RateLimitError(ScrapingError):
    """Raised when rate limited by the target site."""
    pass


class BlockedError(ScrapingError):
    """Raised when blocked by the target site."""
    pass


class BaseScraper(ABC):
    """
    Abstract base class for job scrapers.
    
    Implements common functionality:
    - User agent rotation
    - Rate limiting with random delays
    - Exponential backoff on failures
    - Progress checkpointing
    - Proxy support
    """
    
    # User agents for rotation
    _ua = UserAgent()
    
    # Common headers
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    def __init__(
        self,
        headless: bool = True,
        use_proxy: bool = False,
        proxy_url: Optional[str] = None,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        max_retries: int = 3,
        checkpoint_dir: Optional[str] = None,
    ):
        """
        Initialize the scraper.
        
        Args:
            headless: Run browser in headless mode
            use_proxy: Whether to use proxy
            proxy_url: Proxy URL if using proxy
            delay_min: Minimum delay between requests (seconds)
            delay_max: Maximum delay between requests (seconds)
            max_retries: Maximum number of retries per request
            checkpoint_dir: Directory to save checkpoints
        """
        self.headless = headless
        self.use_proxy = use_proxy or settings.use_proxy
        self.proxy_url = proxy_url or settings.proxy_url
        self.delay_min = delay_min or settings.scraping_delay_min
        self.delay_max = delay_max or settings.scraping_delay_max
        self.max_retries = max_retries
        
        # Checkpoint directory
        self.checkpoint_dir = Path(checkpoint_dir or settings.scraped_jobs_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self._browser = None
        self._context = None
        self._page = None
        self._jobs_scraped: List[Dict[str, Any]] = []
        self._current_page = 0
        self._session_id = self._generate_session_id()
        
        self.logger = logger.bind(scraper=self.__class__.__name__)
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID for checkpointing."""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(f"{self.__class__.__name__}_{timestamp}".encode()).hexdigest()[:8]
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        try:
            return self._ua.random
        except Exception:
            # Fallback user agents
            fallback_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            ]
            return random.choice(fallback_agents)
    
    async def random_delay(self, multiplier: float = 1.0) -> None:
        """Add random delay between requests to avoid detection."""
        delay = random.uniform(self.delay_min, self.delay_max) * multiplier
        self.logger.debug("Waiting", delay=delay)
        await asyncio.sleep(delay)
    
    async def init_browser(self) -> None:
        """Initialize Playwright browser with anti-detection measures."""
        from playwright.async_api import async_playwright
        
        self.logger.info("Initializing browser")
        
        self._playwright = await async_playwright().start()
        
        # Browser launch options
        launch_options = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ]
        }
        
        # Add proxy if configured
        if self.use_proxy and self.proxy_url:
            launch_options["proxy"] = {"server": self.proxy_url}
        
        self._browser = await self._playwright.chromium.launch(**launch_options)
        
        # Create context with anti-detection settings
        context_options = {
            "user_agent": self.get_random_user_agent(),
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone_id": "Asia/Kolkata",
            "permissions": ["geolocation"],
            "geolocation": {"latitude": 12.9716, "longitude": 77.5946},  # Bangalore
        }
        
        self._context = await self._browser.new_context(**context_options)
        
        # Add anti-detection scripts
        await self._context.add_init_script("""
            // Override webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Override chrome property
            window.chrome = {
                runtime: {}
            };
        """)
        
        self._page = await self._context.new_page()
        
        # Set extra headers
        await self._page.set_extra_http_headers(self.DEFAULT_HEADERS)
        
        self.logger.info("Browser initialized")
    
    async def close_browser(self) -> None:
        """Close browser and cleanup resources."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if hasattr(self, '_playwright'):
            await self._playwright.stop()
        
        self.logger.info("Browser closed")
    
    async def navigate_with_retry(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
    ) -> bool:
        """
        Navigate to URL with retry logic.
        
        Args:
            url: URL to navigate to
            wait_until: Wait condition (load, domcontentloaded, networkidle)
            timeout: Timeout in milliseconds
            
        Returns:
            True if navigation successful
        """
        for attempt in range(self.max_retries):
            try:
                self.logger.info("Navigating", url=url, attempt=attempt + 1)
                
                response = await self._page.goto(
                    url,
                    wait_until=wait_until,
                    timeout=timeout
                )
                
                if response and response.status == 429:
                    raise RateLimitError("Rate limited")
                
                if response and response.status == 403:
                    raise BlockedError("Access blocked")
                
                # Check for CAPTCHA or block pages
                content = await self._page.content()
                if self._is_blocked(content):
                    raise BlockedError("Detected blocking page")
                
                await self.random_delay()
                return True
                
            except RateLimitError:
                wait_time = (2 ** attempt) * 30  # Exponential backoff
                self.logger.warning("Rate limited, waiting", wait_time=wait_time)
                await asyncio.sleep(wait_time)
                
                # Rotate user agent
                await self._context.close()
                await self._setup_new_context()
                
            except BlockedError:
                self.logger.error("Blocked by target site")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(60)
                    await self._setup_new_context()
                else:
                    raise
                    
            except Exception as e:
                self.logger.error("Navigation failed", error=str(e))
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    raise ScrapingError(f"Failed to navigate to {url}: {e}")
        
        return False
    
    async def _setup_new_context(self) -> None:
        """Set up a new browser context with fresh user agent."""
        self._context = await self._browser.new_context(
            user_agent=self.get_random_user_agent(),
            viewport={"width": 1920, "height": 1080},
        )
        self._page = await self._context.new_page()
        await self._page.set_extra_http_headers(self.DEFAULT_HEADERS)
    
    def _is_blocked(self, content: str) -> bool:
        """Check if page content indicates blocking."""
        block_indicators = [
            "captcha",
            "robot",
            "blocked",
            "access denied",
            "unusual traffic",
            "verify you're human",
            "security check",
        ]
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in block_indicators)
    
    # ========================================================================
    # Checkpoint Methods
    # ========================================================================
    
    def _get_checkpoint_path(self, keyword: str, location: str = "") -> Path:
        """Get checkpoint file path for a scraping session."""
        safe_keyword = "".join(c if c.isalnum() else "_" for c in keyword)
        safe_location = "".join(c if c.isalnum() else "_" for c in location) if location else "any"
        filename = f"{self.platform_name}_{safe_keyword}_{safe_location}_{self._session_id}.json"
        return self.checkpoint_dir / filename
    
    def save_checkpoint(
        self,
        keyword: str,
        location: str,
        current_page: int,
        jobs: List[Dict[str, Any]]
    ) -> None:
        """Save scraping progress to checkpoint file."""
        checkpoint_data = {
            "platform": self.platform_name,
            "keyword": keyword,
            "location": location,
            "current_page": current_page,
            "jobs_count": len(jobs),
            "jobs": jobs,
            "timestamp": datetime.now().isoformat(),
        }
        
        checkpoint_path = self._get_checkpoint_path(keyword, location)
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info("Checkpoint saved", path=str(checkpoint_path), jobs=len(jobs))
    
    def load_checkpoint(self, keyword: str, location: str = "") -> Optional[Dict[str, Any]]:
        """Load checkpoint if exists and is recent (< 1 hour old)."""
        checkpoint_path = self._get_checkpoint_path(keyword, location)
        
        if not checkpoint_path.exists():
            return None
        
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
            
            # Check if checkpoint is recent
            timestamp = datetime.fromisoformat(checkpoint["timestamp"])
            age_hours = (datetime.now() - timestamp).total_seconds() / 3600
            
            if age_hours > 1:
                self.logger.info("Checkpoint too old, starting fresh", age_hours=age_hours)
                return None
            
            self.logger.info(
                "Loaded checkpoint",
                page=checkpoint["current_page"],
                jobs=checkpoint["jobs_count"]
            )
            return checkpoint
            
        except Exception as e:
            self.logger.warning("Failed to load checkpoint", error=str(e))
            return None
    
    def save_to_json(self, jobs: List[Dict[str, Any]], filename: str) -> str:
        """Save scraped jobs to JSON file."""
        output_path = self.checkpoint_dir / filename
        
        output_data = {
            "platform": self.platform_name,
            "scraped_at": datetime.now().isoformat(),
            "total_jobs": len(jobs),
            "jobs": jobs,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info("Jobs saved", path=str(output_path), count=len(jobs))
        return str(output_path)
    
    # ========================================================================
    # Abstract Methods (to be implemented by subclasses)
    # ========================================================================
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return platform name (e.g., 'naukri', 'linkedin')."""
        pass
    
    @abstractmethod
    def build_search_url(
        self,
        keyword: str,
        location: Optional[str] = None,
        experience_level: Optional[str] = None,
        page: int = 1,
        **kwargs
    ) -> str:
        """Build search URL for the platform."""
        pass
    
    @abstractmethod
    async def parse_job_card(self, job_element) -> Optional[Dict[str, Any]]:
        """Parse a single job card element into structured data."""
        pass
    
    @abstractmethod
    async def get_job_cards(self) -> List:
        """Get all job card elements from current page."""
        pass
    
    @abstractmethod
    async def has_next_page(self) -> bool:
        """Check if there's a next page of results."""
        pass
    
    @abstractmethod
    async def go_to_next_page(self) -> bool:
        """Navigate to the next page of results."""
        pass
    
    # ========================================================================
    # Main Scraping Method
    # ========================================================================
    
    async def scrape_jobs(
        self,
        keyword: str,
        location: Optional[str] = None,
        experience_level: Optional[str] = None,
        num_pages: int = 5,
        resume_from_checkpoint: bool = True,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Scrape jobs from the platform.
        
        Args:
            keyword: Job search keyword
            location: Location filter
            experience_level: Experience level filter
            num_pages: Maximum number of pages to scrape
            resume_from_checkpoint: Whether to resume from checkpoint
            progress_callback: Callback for progress updates (page, total_pages, jobs_found)
            **kwargs: Additional platform-specific parameters
            
        Returns:
            List of job dictionaries
        """
        all_jobs = []
        start_page = 1
        
        # Check for checkpoint
        if resume_from_checkpoint:
            checkpoint = self.load_checkpoint(keyword, location or "")
            if checkpoint:
                all_jobs = checkpoint.get("jobs", [])
                start_page = checkpoint.get("current_page", 1) + 1
                self.logger.info(
                    "Resuming from checkpoint",
                    start_page=start_page,
                    existing_jobs=len(all_jobs)
                )
        
        try:
            await self.init_browser()
            
            for page_num in range(start_page, num_pages + 1):
                self.logger.info(
                    "Scraping page",
                    page=page_num,
                    total_pages=num_pages,
                    jobs_so_far=len(all_jobs)
                )
                
                # Build and navigate to search URL
                search_url = self.build_search_url(
                    keyword=keyword,
                    location=location,
                    experience_level=experience_level,
                    page=page_num,
                    **kwargs
                )
                
                success = await self.navigate_with_retry(search_url)
                if not success:
                    self.logger.error("Failed to load page", page=page_num)
                    break
                
                # Get and parse job cards
                job_cards = await self.get_job_cards()
                self.logger.info("Found job cards", count=len(job_cards))
                
                if not job_cards:
                    self.logger.info("No more job cards found, stopping")
                    break
                
                # Parse each job card
                for card in job_cards:
                    try:
                        job_data = await self.parse_job_card(card)
                        if job_data:
                            # Add metadata
                            job_data["scraped_at"] = datetime.now().isoformat()
                            job_data["source"] = self.platform_name
                            job_data["search_keyword"] = keyword
                            job_data["search_location"] = location
                            
                            # Deduplicate by URL
                            existing_urls = {j.get("job_url") for j in all_jobs}
                            if job_data.get("job_url") not in existing_urls:
                                all_jobs.append(job_data)
                                
                    except Exception as e:
                        self.logger.warning("Failed to parse job card", error=str(e))
                        continue
                
                # Progress callback
                if progress_callback:
                    progress_callback(page_num, num_pages, len(all_jobs))
                
                # Save checkpoint
                self.save_checkpoint(keyword, location or "", page_num, all_jobs)
                
                # Check if there's a next page
                if page_num < num_pages:
                    has_next = await self.has_next_page()
                    if not has_next:
                        self.logger.info("No more pages available")
                        break
                    
                    # Random delay before next page
                    await self.random_delay(multiplier=1.5)
            
            self.logger.info("Scraping completed", total_jobs=len(all_jobs))
            return all_jobs
            
        except Exception as e:
            self.logger.error("Scraping failed", error=str(e))
            # Save progress before raising
            if all_jobs:
                self.save_checkpoint(keyword, location or "", self._current_page, all_jobs)
            raise
            
        finally:
            await self.close_browser()
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    @staticmethod
    def clean_text(text: Optional[str]) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        return " ".join(text.strip().split())
    
    @staticmethod
    def parse_salary(salary_str: Optional[str]) -> Dict[str, Optional[int]]:
        """
        Parse salary string into min/max values.
        
        Examples:
            "10-15 LPA" -> {"min": 1000000, "max": 1500000}
            "50,000 - 80,000" -> {"min": 50000, "max": 80000}
        """
        result = {"min": None, "max": None}
        
        if not salary_str:
            return result
        
        import re
        
        # Clean the string
        salary_str = salary_str.upper().replace(",", "").replace(" ", "")
        
        # Pattern for LPA format (e.g., 10-15LPA)
        lpa_pattern = r"(\d+(?:\.\d+)?)-?(\d+(?:\.\d+)?)?L(?:PA|AC)?"
        match = re.search(lpa_pattern, salary_str)
        if match:
            result["min"] = int(float(match.group(1)) * 100000)
            if match.group(2):
                result["max"] = int(float(match.group(2)) * 100000)
            else:
                result["max"] = result["min"]
            return result
        
        # Pattern for K format (e.g., 50K-80K)
        k_pattern = r"(\d+(?:\.\d+)?)-?(\d+(?:\.\d+)?)?K"
        match = re.search(k_pattern, salary_str)
        if match:
            result["min"] = int(float(match.group(1)) * 1000)
            if match.group(2):
                result["max"] = int(float(match.group(2)) * 1000)
            else:
                result["max"] = result["min"]
            return result
        
        # Generic number pattern
        numbers = re.findall(r"\d+", salary_str)
        if len(numbers) >= 2:
            result["min"] = int(numbers[0])
            result["max"] = int(numbers[1])
        elif len(numbers) == 1:
            result["min"] = int(numbers[0])
            result["max"] = int(numbers[0])
        
        return result
    
    @staticmethod
    def parse_experience(exp_str: Optional[str]) -> Dict[str, Optional[int]]:
        """
        Parse experience string into min/max years.
        
        Examples:
            "3-5 years" -> {"min": 3, "max": 5}
            "5+ years" -> {"min": 5, "max": None}
        """
        result = {"min": None, "max": None}
        
        if not exp_str:
            return result
        
        import re
        
        # Clean the string
        exp_str = exp_str.lower().replace(" ", "")
        
        # Pattern for range (e.g., 3-5years)
        range_pattern = r"(\d+)-(\d+)"
        match = re.search(range_pattern, exp_str)
        if match:
            result["min"] = int(match.group(1))
            result["max"] = int(match.group(2))
            return result
        
        # Pattern for 5+ years
        plus_pattern = r"(\d+)\+"
        match = re.search(plus_pattern, exp_str)
        if match:
            result["min"] = int(match.group(1))
            return result
        
        # Single number
        single_pattern = r"(\d+)"
        match = re.search(single_pattern, exp_str)
        if match:
            result["min"] = int(match.group(1))
            result["max"] = int(match.group(1))
        
        return result

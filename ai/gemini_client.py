"""
Gemini AI Client with rate limiting and caching.
Uses gemini-2.0-flash-exp (free tier).
"""
import json
import time
import hashlib
from datetime import datetime, date
from typing import Dict, Any, Optional, Callable
from functools import wraps
import structlog

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings


logger = structlog.get_logger(__name__)


# In-memory cache (use Redis in production)
_cache: Dict[str, Any] = {}
_daily_usage: Dict[str, int] = {}
_last_request_time: float = 0


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""
    pass


class QuotaExceededError(Exception):
    """Raised when daily quota is exceeded."""
    pass


class GeminiClient:
    """
    Gemini AI client with rate limiting, caching, and retry logic.
    
    Features:
    - Rate limiting: 14 requests/min (buffer below 15)
    - Daily limit: 1400 requests/day (buffer below 1500)
    - Automatic retry with exponential backoff
    - Response caching to reduce API calls
    - Comprehensive logging
    """
    
    MODEL = "gemini-2.0-flash-exp"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini client."""
        self.api_key = api_key or settings.gemini_api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.MODEL)
        self.logger = logger.bind(component="GeminiClient")
        
        # Rate limiting settings
        self.requests_per_minute = getattr(settings, 'rate_limit_rpm', 14)
        self.max_daily_requests = getattr(settings, 'max_daily_requests', 1400)
        self.min_request_interval = 60.0 / self.requests_per_minute
    
    def _get_cache_key(self, operation: str, data: str) -> str:
        """Generate cache key."""
        hash_value = hashlib.md5(data.encode()).hexdigest()
        return f"{operation}:{hash_value}"
    
    def _get_cached(self, operation: str, data: str) -> Optional[Any]:
        """Get cached result."""
        key = self._get_cache_key(operation, data)
        result = _cache.get(key)
        if result:
            self.logger.debug("Cache hit", operation=operation, key=key[:16])
        return result
    
    def _set_cache(self, operation: str, data: str, result: Any) -> None:
        """Cache result."""
        key = self._get_cache_key(operation, data)
        _cache[key] = result
    
    def _get_daily_usage(self) -> int:
        """Get today's usage count."""
        today = date.today().isoformat()
        return _daily_usage.get(today, 0)
    
    def _increment_usage(self) -> int:
        """Increment daily usage."""
        today = date.today().isoformat()
        _daily_usage[today] = _daily_usage.get(today, 0) + 1
        return _daily_usage[today]
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        global _last_request_time
        
        # Check daily limit
        if self._get_daily_usage() >= self.max_daily_requests:
            raise QuotaExceededError(
                f"Daily limit of {self.max_daily_requests} requests exceeded"
            )
        
        # Enforce minimum interval between requests
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            self.logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        _last_request_time = time.time()
    
    def _clean_json_response(self, text: str) -> str:
        """Clean Gemini response that might be wrapped in markdown."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError,))
    )
    def _generate(self, prompt: str, operation: str) -> str:
        """Generate response with retry logic."""
        self._rate_limit()
        
        try:
            self.logger.info("Generating response", operation=operation)
            response = self.model.generate_content(prompt)
            self._increment_usage()
            
            self.logger.info(
                "Response generated",
                operation=operation,
                usage=self._get_daily_usage()
            )
            
            return response.text
            
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                self.logger.warning("Rate limit hit, retrying...")
                raise RateLimitError(str(e))
            raise
    
    def analyze_jd(self, job_description: str) -> Dict[str, Any]:
        """
        Analyze job description.
        
        Returns structured data: skills, experience, responsibilities, keywords.
        """
        # Check cache
        cached = self._get_cached("jd_analysis", job_description)
        if cached:
            return cached
        
        prompt = f"""Analyze this job description and extract key information.

Job Description:
{job_description}

Return JSON with this exact structure:
{{
    "technical_skills": ["skill1", "skill2"],
    "soft_skills": ["skill1", "skill2"],
    "experience_level": "entry|mid|senior|lead",
    "years_required": null or number,
    "key_responsibilities": ["resp1", "resp2"],
    "keywords": ["keyword1", "keyword2"],
    "education": "required education",
    "red_flags": ["any concerning aspects"],
    "salary_range": "if mentioned",
    "remote_policy": "remote|hybrid|onsite|not specified"
}}

Output only valid JSON, no markdown."""

        response = self._generate(prompt, "jd_analysis")
        cleaned = self._clean_json_response(response)
        
        try:
            result = json.loads(cleaned)
            self._set_cache("jd_analysis", job_description, result)
            return result
        except json.JSONDecodeError:
            self.logger.error("Failed to parse JD analysis", response=cleaned[:200])
            # Return basic structure on parse failure
            return {
                "technical_skills": [],
                "soft_skills": [],
                "experience_level": "mid",
                "keywords": [],
                "key_responsibilities": [],
                "red_flags": ["Failed to parse job description"],
            }
    
    def tailor_resume(
        self,
        base_resume: str,
        job_description: str,
        job_title: str,
        company: str
    ) -> str:
        """
        Tailor resume for specific job.
        
        Returns plain text resume ready to use.
        """
        cache_key = f"{base_resume[:100]}|{job_description[:100]}|{job_title}"
        cached = self._get_cached("tailor_resume", cache_key)
        if cached:
            return cached
        
        prompt = f"""Task: Tailor resume for job posting.

Job: {job_title} at {company}

Job Description:
{job_description}

Base Resume:
{base_resume}

Instructions:
1. Reorder bullet points (most relevant first)
2. Add keywords from job description naturally
3. Emphasize matching skills and experience
4. Keep all facts truthful - do not fabricate
5. Make it ATS-friendly
6. Keep format clean and professional

Output: Plain text resume ready to use. No markdown formatting."""

        result = self._generate(prompt, "tailor_resume")
        self._set_cache("tailor_resume", cache_key, result)
        return result
    
    def generate_cover_letter(
        self,
        job_title: str,
        company: str,
        job_description: str,
        your_background: str,
        tone: str = "professional"
    ) -> str:
        """
        Generate personalized cover letter.
        
        Tones: professional, conversational, enthusiastic
        """
        cache_key = f"{job_title}|{company}|{your_background[:100]}|{tone}"
        cached = self._get_cached("cover_letter", cache_key)
        if cached:
            return cached
        
        tone_instructions = {
            "professional": "Use formal, polished language. Be direct and confident.",
            "conversational": "Use friendly but professional tone. Be personable.",
            "enthusiastic": "Show genuine excitement. Use energetic language."
        }
        
        prompt = f"""Task: Write a cover letter.

Position: {job_title} at {company}
Tone: {tone_instructions.get(tone, tone_instructions["professional"])}

Job Requirements:
{job_description[:1000]}

Candidate Background:
{your_background}

Instructions:
1. Start with a specific hook about the company/role (not "I am writing to apply")
2. Connect 2-3 experiences to job requirements with specifics
3. Show understanding of their needs
4. End with clear call to action
5. Keep to 3 paragraphs, under 300 words
6. Avoid generic phrases

Output: Cover letter text only, no headers or signatures."""

        result = self._generate(prompt, "cover_letter")
        self._set_cache("cover_letter", cache_key, result)
        return result
    
    def calculate_match_score(
        self,
        base_resume: str,
        job_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate match score between resume and job.
        
        Returns score (0-100), breakdown, and suggestions.
        """
        cache_key = f"{base_resume[:200]}|{json.dumps(job_requirements)[:200]}"
        cached = self._get_cached("match_score", cache_key)
        if cached:
            return cached
        
        prompt = f"""Task: Calculate job match score.

Job Requirements:
{json.dumps(job_requirements, indent=2)}

Candidate Resume:
{base_resume}

Scoring weights:
- Skills overlap: 40%
- Experience match: 20%
- Education fit: 15%
- Project relevance: 15%
- Location/remote fit: 10%

Return JSON:
{{
    "overall_score": 0-100,
    "breakdown": {{
        "skills": {{"score": 0-100, "matched": ["skill1"], "missing": ["skill2"]}},
        "experience": {{"score": 0-100, "notes": "explanation"}},
        "education": {{"score": 0-100, "notes": "explanation"}},
        "projects": {{"score": 0-100, "relevant": ["project1"]}},
        "location": {{"score": 0-100, "notes": "explanation"}}
    }},
    "suggestions": ["how to improve match"],
    "strengths": ["candidate strengths for this role"],
    "recommendation": "strong match|good match|fair match|weak match"
}}

Output only valid JSON."""

        response = self._generate(prompt, "match_score")
        cleaned = self._clean_json_response(response)
        
        try:
            result = json.loads(cleaned)
            self._set_cache("match_score", cache_key, result)
            return result
        except json.JSONDecodeError:
            self.logger.error("Failed to parse match score", response=cleaned[:200])
            return {
                "overall_score": 50,
                "breakdown": {},
                "suggestions": ["Unable to calculate detailed score"],
                "recommendation": "fair match"
            }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        daily_usage = self._get_daily_usage()
        return {
            "requests_today": daily_usage,
            "daily_limit": self.max_daily_requests,
            "remaining": self.max_daily_requests - daily_usage,
            "percentage_used": round((daily_usage / self.max_daily_requests) * 100, 1),
            "cache_size": len(_cache),
        }


# Singleton instance
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create Gemini client."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client

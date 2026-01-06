"""
Job Description Analyzer using Claude Sonnet 4.
Extracts structured information from job descriptions with caching.
"""
import json
import hashlib
from typing import Optional, Dict, Any, List
import structlog

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


logger = structlog.get_logger(__name__)


# In-memory cache for JD analyses (use Redis in production)
_jd_cache: Dict[str, Dict[str, Any]] = {}


class JDAnalyzer:
    """
    Analyzes job descriptions using Claude Sonnet 4.
    
    Extracts:
    - Required and preferred skills
    - Experience requirements
    - Key responsibilities
    - ATS keywords
    - Soft skills
    - Red flags
    - Company culture indicators
    """
    
    ANALYSIS_PROMPT = """You are an expert job description analyzer. Analyze the following job description and extract structured information.

<job_description>
{job_description}
</job_description>

Analyze this job description and provide a JSON response with the following structure:

{{
    "required_skills": {{
        "technical": ["list of required technical skills"],
        "tools": ["specific tools, frameworks, languages mentioned as required"],
        "certifications": ["any required certifications"]
    }},
    "preferred_skills": {{
        "technical": ["nice-to-have technical skills"],
        "tools": ["preferred tools/technologies"],
        "certifications": ["preferred certifications"]
    }},
    "experience": {{
        "years_min": <minimum years as integer or null>,
        "years_max": <maximum years as integer or null>,
        "level": "fresher|junior|mid|senior|lead|principal",
        "specific_experience": ["specific types of experience required, e.g., 'ML model deployment', 'team leadership'"]
    }},
    "responsibilities": [
        "key responsibility 1",
        "key responsibility 2"
    ],
    "ats_keywords": [
        "important keywords for ATS matching - should include skills, tools, and key phrases"
    ],
    "soft_skills": [
        "communication",
        "teamwork",
        "etc."
    ],
    "education": {{
        "required": "minimum education requirement",
        "preferred": "preferred education",
        "fields": ["relevant fields of study"]
    }},
    "company_culture": {{
        "work_style": "remote|hybrid|onsite|flexible",
        "team_size": "startup|small|medium|large|enterprise",
        "pace": "fast-paced|moderate|relaxed",
        "values": ["mentioned company values"]
    }},
    "compensation": {{
        "salary_mentioned": true|false,
        "benefits_mentioned": ["list of benefits if mentioned"],
        "equity_mentioned": true|false
    }},
    "red_flags": [
        "any concerning aspects like unrealistic expectations, underpaid indicators, vague descriptions"
    ],
    "job_type": "full-time|part-time|contract|internship|freelance",
    "seniority_assessment": {{
        "level": "entry|mid|senior|lead|executive",
        "justification": "brief explanation of why this level was determined"
    }},
    "match_difficulty": {{
        "score": <1-10 difficulty to match this role>,
        "factors": ["what makes this easy or hard to fill"]
    }}
}}

Important guidelines:
1. Be specific with skills - don't generalize (e.g., "Python 3.x" not just "programming")
2. Extract actual keywords from the JD for ATS matching
3. Be honest about red flags - look for unrealistic combinations, low pay signals, excessive requirements
4. If information is not available, use null or empty arrays
5. Respond ONLY with valid JSON, no markdown or explanations

Analyze the job description now:"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Anthropic API key."""
        self.api_key = api_key or settings.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
        self.model = settings.claude_sonnet_model
        self.logger = logger.bind(component="JDAnalyzer")
    
    def _get_cache_key(self, job_description: str) -> str:
        """Generate cache key from job description."""
        # Normalize and hash
        normalized = " ".join(job_description.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis if available."""
        return _jd_cache.get(cache_key)
    
    def _set_cache(self, cache_key: str, analysis: Dict[str, Any]) -> None:
        """Cache the analysis result."""
        _jd_cache[cache_key] = analysis
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def analyze(
        self,
        job_description: str,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze a job description and extract structured information.
        
        Args:
            job_description: The full job description text
            use_cache: Whether to use cached results
            
        Returns:
            Structured analysis dict
        """
        if not self.client:
            raise ValueError("Anthropic API key not configured")
        
        if not job_description or len(job_description.strip()) < 50:
            raise ValueError("Job description too short to analyze")
        
        # Check cache
        cache_key = self._get_cache_key(job_description)
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached:
                self.logger.info("Using cached JD analysis", cache_key=cache_key[:8])
                return cached
        
        self.logger.info("Analyzing job description", length=len(job_description))
        
        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=settings.max_tokens_jd_analysis,
                messages=[{
                    "role": "user",
                    "content": self.ANALYSIS_PROMPT.format(job_description=job_description)
                }]
            )
            
            # Track costs
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens
            
            self.logger.info(
                "JD analysis complete",
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            # Parse response
            response_text = message.content[0].text
            
            # Clean up response (remove any markdown formatting)
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
            
            analysis = json.loads(response_text)
            
            # Add metadata
            analysis["_metadata"] = {
                "model": self.model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_key": cache_key,
            }
            
            # Cache the result
            self._set_cache(cache_key, analysis)
            
            return analysis
            
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse JD analysis response", error=str(e))
            raise ValueError(f"Invalid response from AI: {e}")
        except Exception as e:
            self.logger.error("JD analysis failed", error=str(e))
            raise
    
    def extract_keywords(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract all keywords from analysis for matching."""
        keywords = set()
        
        # Technical skills
        for skill_type in ["required_skills", "preferred_skills"]:
            skills = analysis.get(skill_type, {})
            keywords.update(skills.get("technical", []))
            keywords.update(skills.get("tools", []))
        
        # ATS keywords
        keywords.update(analysis.get("ats_keywords", []))
        
        # Soft skills
        keywords.update(analysis.get("soft_skills", []))
        
        return list(keywords)
    
    def get_difficulty_summary(self, analysis: Dict[str, Any]) -> str:
        """Get human-readable difficulty summary."""
        difficulty = analysis.get("match_difficulty", {})
        score = difficulty.get("score", 5)
        factors = difficulty.get("factors", [])
        
        if score <= 3:
            level = "Easy"
        elif score <= 6:
            level = "Moderate"
        else:
            level = "Challenging"
        
        summary = f"{level} ({score}/10)"
        if factors:
            summary += f" - {', '.join(factors[:2])}"
        
        return summary


# ============================================================================
# Convenience Function
# ============================================================================

async def analyze_job_description(
    job_description: str,
    api_key: Optional[str] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function to analyze a job description.
    
    Example:
        analysis = await analyze_job_description('''
            We are looking for a Senior Python Developer with 5+ years of experience.
            You should have expertise in Django, FastAPI, and PostgreSQL.
            Experience with AWS and Docker is preferred.
        ''')
        print(analysis['required_skills']['technical'])
    """
    analyzer = JDAnalyzer(api_key=api_key)
    return await analyzer.analyze(job_description, use_cache=use_cache)

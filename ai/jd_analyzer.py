"""
Job Description Analyzer using Google Gemini.
Extracts structured information from job descriptions with caching.
"""
import json
import hashlib
from typing import Optional, Dict, Any, List
import structlog

from ai.gemini_client import get_gemini_client, GeminiClient


logger = structlog.get_logger(__name__)


class JDAnalyzer:
    """
    Analyzes job descriptions using Gemini.
    
    Extracts:
    - Required and preferred skills
    - Experience requirements
    - Key responsibilities
    - ATS keywords
    - Red flags
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional API key."""
        if api_key:
            self.client = GeminiClient(api_key=api_key)
        else:
            self.client = get_gemini_client()
        self.logger = logger.bind(component="JDAnalyzer")
    
    async def analyze(
        self,
        job_description: str,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze a job description and extract structured information.
        
        Args:
            job_description: The full job description text
            use_cache: Whether to use cached results (handled by client)
            
        Returns:
            Structured analysis dict
        """
        if not job_description or len(job_description.strip()) < 50:
            raise ValueError("Job description too short to analyze")
        
        self.logger.info("Analyzing job description", length=len(job_description))
        
        result = self.client.analyze_jd(job_description)
        
        # Normalize keys for backward compatibility
        normalized = {
            "required_skills": {
                "technical": result.get("technical_skills", []),
                "tools": [],
                "certifications": [],
            },
            "preferred_skills": {
                "technical": [],
                "tools": [],
                "certifications": [],
            },
            "experience": {
                "years_min": result.get("years_required"),
                "years_max": None,
                "level": result.get("experience_level", "mid"),
                "specific_experience": [],
            },
            "responsibilities": result.get("key_responsibilities", []),
            "ats_keywords": result.get("keywords", []),
            "soft_skills": result.get("soft_skills", []),
            "education": {
                "required": result.get("education", ""),
                "preferred": "",
                "fields": [],
            },
            "company_culture": {
                "work_style": result.get("remote_policy", "not specified"),
                "team_size": "unknown",
                "pace": "unknown",
                "values": [],
            },
            "red_flags": result.get("red_flags", []),
            "_metadata": {
                "model": "gemini-2.0-flash-exp",
                "cached": False,
            }
        }
        
        return normalized
    
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


# Convenience function
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
        ''')
        print(analysis['required_skills']['technical'])
    """
    analyzer = JDAnalyzer(api_key=api_key)
    return await analyzer.analyze(job_description, use_cache=use_cache)

"""
Match Scorer using Google Gemini.
Calculates job-candidate fit with weighted factors.
"""
import json
from typing import Optional, Dict, Any, List, Set
import structlog

from ai.gemini_client import get_gemini_client, GeminiClient


logger = structlog.get_logger(__name__)


class MatchScorer:
    """
    Calculates match score between a candidate and job using Gemini.
    
    Factors and weights:
    - Skills overlap: 40%
    - Experience match: 20%
    - Education fit: 15%
    - Project relevance: 15%
    - Location preference: 10%
    """
    
    WEIGHTS = {
        "skills": 0.40,
        "experience": 0.20,
        "education": 0.15,
        "projects": 0.15,
        "location": 0.10,
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional API key."""
        if api_key:
            self.client = GeminiClient(api_key=api_key)
        else:
            self.client = get_gemini_client()
        self.logger = logger.bind(component="MatchScorer")
    
    async def calculate_score(
        self,
        candidate_profile: str,
        job_description: str,
        job_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate match score between candidate and job.
        
        Args:
            candidate_profile: Resume text or candidate summary
            job_description: Full job description
            job_analysis: Pre-analyzed JD
            
        Returns:
            Detailed match score breakdown
        """
        self.logger.info("Calculating match score")
        
        # Build job requirements
        if job_analysis:
            job_requirements = job_analysis
        else:
            # Analyze JD first
            job_requirements = self.client.analyze_jd(job_description)
        
        # Calculate match score
        result = self.client.calculate_match_score(
            base_resume=candidate_profile,
            job_requirements=job_requirements
        )
        
        # Add metadata
        result["metadata"] = {
            "model": "gemini-2.0-flash-exp",
            "weights_used": self.WEIGHTS,
            "cost_usd": 0.0,
        }
        
        return result
    
    def quick_score(
        self,
        candidate_skills: Set[str],
        job_analysis: Dict[str, Any],
    ) -> int:
        """
        Calculate a quick match score without API call.
        Uses keyword overlap for fast matching.
        """
        # Get required skills from analysis
        required = set()
        
        if "required_skills" in job_analysis:
            skills = job_analysis["required_skills"]
            required.update(s.lower() for s in skills.get("technical", []))
            required.update(s.lower() for s in skills.get("tools", []))
        
        if "technical_skills" in job_analysis:
            required.update(s.lower() for s in job_analysis["technical_skills"])
        
        if not required:
            return 50  # Neutral if no requirements
        
        # Calculate overlap
        candidate_lower = {s.lower() for s in candidate_skills}
        overlap = len(candidate_lower & required) / len(required)
        
        return min(100, max(0, round(overlap * 100)))
    
    def get_match_level(self, score: int) -> str:
        """Convert numeric score to match level."""
        if score >= 85:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 55:
            return "moderate"
        elif score >= 40:
            return "weak"
        else:
            return "poor"
    
    def get_recommendation(self, score: int) -> str:
        """Get recommendation based on score."""
        if score >= 80:
            return "strong match"
        elif score >= 65:
            return "good match"
        elif score >= 50:
            return "fair match"
        else:
            return "weak match"


# Convenience function
async def calculate_match_score(
    candidate_profile: str,
    job_description: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to calculate match score.
    
    Example:
        result = await calculate_match_score(
            candidate_profile="5 years Python, Django, AWS...",
            job_description="Looking for Senior Python Developer..."
        )
        print(f"Match Score: {result['overall_score']}")
    """
    scorer = MatchScorer(api_key=api_key)
    return await scorer.calculate_score(
        candidate_profile=candidate_profile,
        job_description=job_description,
    )

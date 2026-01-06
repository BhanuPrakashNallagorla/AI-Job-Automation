"""
Match Scorer for job-candidate fit calculation.
Uses weighted factors to calculate match score with detailed breakdown.
"""
import json
from typing import Optional, Dict, Any, List, Set
import structlog

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


logger = structlog.get_logger(__name__)


class MatchScorer:
    """
    Calculates match score between a candidate and job.
    
    Factors and weights:
    - Hard skills overlap: 40%
    - Experience level match: 20%
    - Soft skills match: 15%
    - Education requirements: 15%
    - Location preference: 10%
    """
    
    WEIGHTS = {
        "hard_skills": 0.40,
        "experience": 0.20,
        "soft_skills": 0.15,
        "education": 0.15,
        "location": 0.10,
    }
    
    SCORING_PROMPT = """You are an expert at evaluating candidate-job fit. Analyze the match between this candidate and job.

<candidate_profile>
{candidate_profile}
</candidate_profile>

<job_analysis>
{job_analysis}
</job_analysis>

<job_description>
{job_description}
</job_description>

Evaluate the match and provide scores (0-100) for each factor:

1. HARD SKILLS (Technical skills, tools, frameworks)
   - Compare candidate's technical skills with required and preferred skills
   - Consider equivalent technologies
   - Weight required skills higher than preferred

2. EXPERIENCE (Years and type of experience)
   - Compare years of experience with requirements
   - Consider relevance of experience type
   - Account for transferable experience

3. SOFT SKILLS (Communication, leadership, teamwork, etc.)
   - Identify soft skills from candidate profile
   - Match against job requirements
   - Consider leadership experience if required

4. EDUCATION (Degree, field of study)
   - Match degree level with requirements
   - Consider field of study relevance
   - Account for alternative qualifications (bootcamps, certifications)

5. LOCATION (Location match/willingness to relocate)
   - If remote job, give full score
   - Consider candidate's current location
   - Account for relocation willingness if known

Provide your response in JSON format:

{{
    "scores": {{
        "hard_skills": {{
            "score": <0-100>,
            "matched_skills": ["skill1", "skill2"],
            "missing_required": ["missing skill 1"],
            "missing_preferred": ["nice-to-have 1"],
            "equivalent_skills": {{"candidate_skill": "equivalent_required_skill"}},
            "notes": "explanation"
        }},
        "experience": {{
            "score": <0-100>,
            "years_required": <number or null>,
            "years_candidate": <estimated or null>,
            "experience_gaps": ["gap 1"],
            "relevant_experience": ["relevant exp 1"],
            "notes": "explanation"
        }},
        "soft_skills": {{
            "score": <0-100>,
            "matched": ["skill1"],
            "potential": ["skill that could be inferred"],
            "notes": "explanation"
        }},
        "education": {{
            "score": <0-100>,
            "meets_minimum": true|false,
            "field_match": true|false,
            "notes": "explanation"
        }},
        "location": {{
            "score": <0-100>,
            "job_location": "location or remote",
            "candidate_location": "location if known",
            "is_remote": true|false,
            "notes": "explanation"
        }}
    }},
    "overall_score": <weighted average 0-100>,
    "match_level": "excellent|good|moderate|weak|poor",
    "key_strengths": [
        "strength 1",
        "strength 2"
    ],
    "key_gaps": [
        "gap 1 with suggestion to address",
        "gap 2 with suggestion"
    ],
    "improvement_suggestions": [
        {{
            "area": "skill or experience",
            "suggestion": "how to improve match",
            "impact": "potential score increase"
        }}
    ],
    "recommendation": "hire|interview|maybe|pass",
    "confidence": <0-100 confidence in this assessment>
}}

Respond ONLY with valid JSON."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Anthropic API key."""
        self.api_key = api_key or settings.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
        self.model = settings.claude_sonnet_model  # Use Sonnet for cost efficiency
        self.logger = logger.bind(component="MatchScorer")
    
    def extract_skills_from_resume(self, resume_text: str) -> Set[str]:
        """Extract skills from resume text using simple pattern matching."""
        # Common technical skills patterns
        common_skills = {
            "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
            "react", "angular", "vue", "node.js", "django", "flask", "fastapi",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            "sql", "postgresql", "mysql", "mongodb", "redis",
            "machine learning", "deep learning", "nlp", "computer vision",
            "git", "ci/cd", "agile", "scrum",
        }
        
        resume_lower = resume_text.lower()
        found_skills = set()
        
        for skill in common_skills:
            if skill in resume_lower:
                found_skills.add(skill)
        
        return found_skills
    
    def calculate_keyword_overlap(
        self,
        candidate_skills: Set[str],
        required_skills: List[str],
        preferred_skills: List[str],
    ) -> Dict[str, Any]:
        """Calculate skill overlap between candidate and job."""
        candidate_lower = {s.lower() for s in candidate_skills}
        required_lower = {s.lower() for s in required_skills}
        preferred_lower = {s.lower() for s in preferred_skills}
        
        matched_required = candidate_lower & required_lower
        matched_preferred = candidate_lower & preferred_lower
        missing_required = required_lower - candidate_lower
        missing_preferred = preferred_lower - candidate_lower
        
        # Calculate score
        if required_lower:
            required_score = len(matched_required) / len(required_lower) * 100
        else:
            required_score = 100
        
        if preferred_lower:
            preferred_score = len(matched_preferred) / len(preferred_lower) * 100
        else:
            preferred_score = 100
        
        # Weight: 70% required, 30% preferred
        score = required_score * 0.7 + preferred_score * 0.3
        
        return {
            "score": round(score),
            "matched_required": list(matched_required),
            "matched_preferred": list(matched_preferred),
            "missing_required": list(missing_required),
            "missing_preferred": list(missing_preferred),
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
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
            job_analysis: Pre-analyzed JD (from JDAnalyzer)
            
        Returns:
            Detailed match score breakdown
        """
        if not self.client:
            raise ValueError("Anthropic API key not configured")
        
        self.logger.info("Calculating match score")
        
        # Get job analysis if not provided
        if not job_analysis:
            from ai.jd_analyzer import JDAnalyzer
            analyzer = JDAnalyzer(api_key=self.api_key)
            job_analysis = await analyzer.analyze(job_description)
        
        # Build prompt
        prompt = self.SCORING_PROMPT.format(
            candidate_profile=candidate_profile,
            job_analysis=json.dumps(job_analysis, indent=2),
            job_description=job_description,
        )
        
        try:
            # Call Claude
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Track usage
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens
            
            self.logger.info(
                "Match scoring complete",
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            # Parse response
            response_text = message.content[0].text
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
            
            result = json.loads(response_text)
            
            # Add metadata
            result["metadata"] = {
                "model": self.model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "weights_used": self.WEIGHTS,
            }
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse scoring response", error=str(e))
            raise ValueError(f"Invalid response from AI: {e}")
        except Exception as e:
            self.logger.error("Match scoring failed", error=str(e))
            raise
    
    def quick_score(
        self,
        candidate_skills: Set[str],
        job_analysis: Dict[str, Any],
    ) -> int:
        """
        Calculate a quick match score without API call.
        
        Uses keyword overlap for fast matching during bulk job filtering.
        
        Args:
            candidate_skills: Set of candidate's skills
            job_analysis: Analyzed job description
            
        Returns:
            Quick match score 0-100
        """
        # Extract required skills from analysis
        required_skills = job_analysis.get("required_skills", {})
        technical = required_skills.get("technical", [])
        tools = required_skills.get("tools", [])
        
        # Combine all required skills
        all_required = set(s.lower() for s in technical + tools)
        
        # Get preferred skills
        preferred_skills = job_analysis.get("preferred_skills", {})
        preferred_tech = preferred_skills.get("technical", [])
        preferred_tools = preferred_skills.get("tools", [])
        all_preferred = set(s.lower() for s in preferred_tech + preferred_tools)
        
        # Calculate overlap
        candidate_lower = {s.lower() for s in candidate_skills}
        
        if all_required:
            required_overlap = len(candidate_lower & all_required) / len(all_required)
        else:
            required_overlap = 0.5  # Neutral if no requirements specified
        
        if all_preferred:
            preferred_overlap = len(candidate_lower & all_preferred) / len(all_preferred)
        else:
            preferred_overlap = 0.5
        
        # Weight: 70% required, 30% preferred
        score = (required_overlap * 0.7 + preferred_overlap * 0.3) * 100
        
        return min(100, max(0, round(score)))
    
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
        """Get hiring recommendation based on score."""
        if score >= 80:
            return "hire"
        elif score >= 65:
            return "interview"
        elif score >= 50:
            return "maybe"
        else:
            return "pass"


# ============================================================================
# Convenience Function
# ============================================================================

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
        print(f"Recommendation: {result['recommendation']}")
    """
    scorer = MatchScorer(api_key=api_key)
    return await scorer.calculate_score(
        candidate_profile=candidate_profile,
        job_description=job_description,
    )

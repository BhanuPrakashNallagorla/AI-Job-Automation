"""
Cover Letter Generator using Google Gemini.
Generates personalized, non-generic cover letters.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import structlog

from ai.gemini_client import get_gemini_client, GeminiClient
from config import settings


logger = structlog.get_logger(__name__)


class ToneStyle:
    """Cover letter tone options."""
    PROFESSIONAL = "professional"
    CONVERSATIONAL = "conversational"
    ENTHUSIASTIC = "enthusiastic"


class CoverLetterGenerator:
    """
    Generates personalized cover letters using Gemini.
    
    Features:
    - Multiple tone options
    - Non-generic output
    - Company-specific personalization
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional API key."""
        if api_key:
            self.client = GeminiClient(api_key=api_key)
        else:
            self.client = get_gemini_client()
        self.output_dir = Path(settings.cover_letters_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(component="CoverLetterGenerator")
    
    async def generate(
        self,
        job_description: str,
        candidate_background: str,
        company_name: Optional[str] = None,
        job_title: Optional[str] = None,
        company_info: Optional[Dict[str, Any]] = None,
        job_analysis: Optional[Dict[str, Any]] = None,
        tone: str = ToneStyle.PROFESSIONAL,
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized cover letter.
        
        Args:
            job_description: Full job description text
            candidate_background: Candidate's resume text or key experiences
            company_name: Company name
            job_title: Job title
            company_info: Additional company info
            job_analysis: Pre-analyzed JD
            tone: professional, conversational, or enthusiastic
            additional_context: Any additional context
            
        Returns:
            Dict with cover letter text and metadata
        """
        self.logger.info("Generating cover letter", tone=tone)
        
        # Default values
        job_title = job_title or "the position"
        company_name = company_name or "the company"
        
        # Append additional context if provided
        full_background = candidate_background
        if additional_context:
            full_background += f"\n\nAdditional context: {additional_context}"
        
        # Generate cover letter
        cover_letter_text = self.client.generate_cover_letter(
            job_title=job_title,
            company=company_name,
            job_description=job_description,
            your_background=full_background,
            tone=tone
        )
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        company_slug = company_name.lower().replace(" ", "_")[:20]
        filename = f"cover_letter_{company_slug}_{timestamp}.txt"
        output_path = self.output_dir / filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cover_letter_text)
        
        # Count words
        word_count = len(cover_letter_text.split())
        
        return {
            "success": True,
            "cover_letter": {
                "opening": "",  # Gemini returns full text
                "body": "",
                "closing": "",
            },
            "full_text": cover_letter_text,
            "output_path": str(output_path),
            "personalization_elements": [],
            "key_qualifications": [],
            "unique_hooks": [],
            "word_count": word_count,
            "tone": tone,
            "metadata": {
                "model": "gemini-2.0-flash-exp",
                "cost_usd": 0.0,
            }
        }
    
    async def generate_follow_up_email(
        self,
        application_details: Dict[str, Any],
        days_since_application: int,
    ) -> Dict[str, Any]:
        """Generate a follow-up email for an application."""
        job_title = application_details.get('job_title', 'the position')
        company = application_details.get('company', 'your company')
        
        # Use Gemini to generate follow-up
        # For simplicity, generate directly without dedicated method
        result = self.client.generate_cover_letter(
            job_title=job_title,
            company=company,
            job_description=f"Follow up on {job_title} application submitted {days_since_application} days ago.",
            your_background="Following up on my application.",
            tone="professional"
        )
        
        # Parse as email (simple format)
        lines = result.strip().split('\n')
        subject = f"Following Up - {job_title} Application"
        body = result
        
        return {
            "subject": subject,
            "body": body,
            "word_count": len(result.split())
        }


# Convenience function
async def generate_cover_letter(
    job_description: str,
    candidate_background: str,
    company_name: Optional[str] = None,
    tone: str = ToneStyle.PROFESSIONAL,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to generate a cover letter.
    
    Example:
        result = await generate_cover_letter(
            job_description="We are looking for a software engineer...",
            candidate_background="5 years of Python experience...",
            company_name="TechCorp",
            tone="professional"
        )
        print(result['full_text'])
    """
    generator = CoverLetterGenerator(api_key=api_key)
    return await generator.generate(
        job_description=job_description,
        candidate_background=candidate_background,
        company_name=company_name,
        tone=tone,
    )

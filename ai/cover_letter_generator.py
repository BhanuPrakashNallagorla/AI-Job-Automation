"""
Cover Letter Generator using Claude Opus 4.
Generates personalized, non-generic cover letters.
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import structlog

from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


logger = structlog.get_logger(__name__)


class ToneStyle:
    """Cover letter tone options."""
    PROFESSIONAL = "professional"
    CONVERSATIONAL = "conversational"
    ENTHUSIASTIC = "enthusiastic"


class CoverLetterGenerator:
    """
    Generates personalized cover letters using Claude Opus 4.
    
    Features:
    - Avoids generic phrases
    - Company-specific personalization
    - Multiple tone options
    - 3-paragraph structure
    - Research integration
    """
    
    TONE_GUIDELINES = {
        ToneStyle.PROFESSIONAL: """Tone: Professional and polished
- Use formal language but remain personable
- Demonstrate expertise and competence
- Show respect for the company's work
- Keep sentences concise and impactful
- Avoid overly casual expressions""",

        ToneStyle.CONVERSATIONAL: """Tone: Conversational and approachable
- Write like you're having a professional coffee chat
- Use first person naturally
- Show personality while remaining professional
- Be direct and genuine
- Use shorter sentences and natural transitions""",

        ToneStyle.ENTHUSIASTIC: """Tone: Enthusiastic and energetic
- Show genuine excitement about the opportunity
- Use active, dynamic language
- Convey passion for the work
- Be specific about what excites you
- Maintain professionalism while being warm"""
    }
    
    COVER_LETTER_PROMPT = """You are an expert cover letter writer who creates personalized, compelling cover letters that stand out.

IMPORTANT RULES:
1. NEVER use these generic phrases:
   - "I am writing to apply for..."
   - "I am excited to apply..."
   - "I came across this job posting..."
   - "I believe I would be a great fit..."
   - "Please find my resume attached"
   - "Thank you for your consideration"
   - Generic superlatives like "passionate" or "driven" without context

2. Instead:
   - Start with something specific about the company or role
   - Lead with your most relevant accomplishment
   - Show you've researched the company
   - Be specific about what you can contribute

{tone_guidelines}

<your_background>
{candidate_background}
</your_background>

<job_description>
{job_description}
</job_description>

<job_analysis>
{job_analysis}
</job_analysis>

<company_info>
{company_info}
</company_info>

Generate a 3-paragraph cover letter:

PARAGRAPH 1 (Opening - 3-4 sentences):
- Hook with something specific about the company/role (from company_info)
- Briefly introduce yourself with your most relevant qualification
- State why THIS role at THIS company interests you specifically

PARAGRAPH 2 (Body - 4-6 sentences):
- Connect 2-3 specific experiences to the job requirements
- Use concrete numbers and achievements where possible
- Show understanding of their challenges and how you can help
- Reference specific skills from the job description

PARAGRAPH 3 (Closing - 2-3 sentences):
- Summarize your unique value proposition
- Express genuine interest in discussing further
- End with a specific, non-generic call to action

Provide your response in JSON format:

{{
    "cover_letter": {{
        "opening": "first paragraph text",
        "body": "second paragraph text",  
        "closing": "third paragraph text"
    }},
    "full_text": "complete cover letter as a single formatted text",
    "personalization_elements": [
        "specific element 1 used from company research",
        "specific element 2"
    ],
    "key_qualifications_highlighted": [
        "qualification 1",
        "qualification 2"
    ],
    "unique_hooks": [
        "what makes this letter stand out"
    ],
    "word_count": <number>
}}

Respond ONLY with valid JSON."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Anthropic API key."""
        self.api_key = api_key or settings.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
        self.model = settings.claude_opus_model
        self.output_dir = Path(settings.cover_letters_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(component="CoverLetterGenerator")
    
    async def research_company(self, company_name: str) -> Dict[str, Any]:
        """
        Research company for personalization.
        
        In production, this would scrape the company website, 
        LinkedIn, and news articles.
        """
        # Placeholder for company research
        # In production, implement web scraping or use APIs
        return {
            "name": company_name,
            "description": f"Company: {company_name}",
            "recent_news": [],
            "products": [],
            "culture": [],
            "mission": None,
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        job_description: str,
        candidate_background: str,
        company_name: Optional[str] = None,
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
            company_name: Company name for research
            company_info: Pre-researched company info
            job_analysis: Optional pre-analyzed JD
            tone: professional, conversational, or enthusiastic
            additional_context: Any additional context to include
            
        Returns:
            Dict with cover letter text and metadata
        """
        if not self.client:
            raise ValueError("Anthropic API key not configured")
        
        self.logger.info("Generating cover letter", tone=tone)
        
        # Get or research company info
        if not company_info and company_name:
            company_info = await self.research_company(company_name)
        
        company_info = company_info or {}
        
        # Get job analysis if not provided
        if not job_analysis:
            from ai.jd_analyzer import JDAnalyzer
            analyzer = JDAnalyzer(api_key=self.api_key)
            job_analysis = await analyzer.analyze(job_description)
        
        # Get tone guidelines
        tone_guidelines = self.TONE_GUIDELINES.get(
            tone, 
            self.TONE_GUIDELINES[ToneStyle.PROFESSIONAL]
        )
        
        # Build prompt
        prompt = self.COVER_LETTER_PROMPT.format(
            tone_guidelines=tone_guidelines,
            candidate_background=candidate_background,
            job_description=job_description,
            job_analysis=json.dumps(job_analysis, indent=2),
            company_info=json.dumps(company_info, indent=2),
        )
        
        if additional_context:
            prompt += f"\n\nAdditional context:\n{additional_context}"
        
        try:
            # Call Claude Opus
            message = self.client.messages.create(
                model=self.model,
                max_tokens=settings.max_tokens_cover_letter,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Track usage
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens
            
            self.logger.info(
                "Cover letter generated",
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            # Parse response
            response_text = message.content[0].text
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
            
            result = json.loads(response_text)
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_slug = (company_info.get("name", "unknown")
                          .lower().replace(" ", "_")[:20])
            filename = f"cover_letter_{company_slug}_{timestamp}.txt"
            output_path = self.output_dir / filename
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result.get("full_text", ""))
            
            return {
                "success": True,
                "cover_letter": result.get("cover_letter", {}),
                "full_text": result.get("full_text", ""),
                "output_path": str(output_path),
                "personalization_elements": result.get("personalization_elements", []),
                "key_qualifications": result.get("key_qualifications_highlighted", []),
                "unique_hooks": result.get("unique_hooks", []),
                "word_count": result.get("word_count", 0),
                "tone": tone,
                "metadata": {
                    "model": self.model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
            }
            
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse cover letter response", error=str(e))
            raise ValueError(f"Invalid response from AI: {e}")
        except Exception as e:
            self.logger.error("Cover letter generation failed", error=str(e))
            raise
    
    async def generate_follow_up_email(
        self,
        application_details: Dict[str, Any],
        days_since_application: int,
    ) -> Dict[str, Any]:
        """
        Generate a follow-up email for an application.
        
        Args:
            application_details: Job and application info
            days_since_application: Days since applying
            
        Returns:
            Follow-up email text
        """
        prompt = f"""Generate a brief, professional follow-up email for a job application.

Application details:
- Job Title: {application_details.get('job_title', 'the position')}
- Company: {application_details.get('company', 'your company')}
- Applied: {days_since_application} days ago

Guidelines:
- Keep it under 100 words
- Be polite but not pushy
- Reaffirm interest briefly
- Avoid desperation or excessive enthusiasm
- Include a soft call to action

Provide the email in JSON format:
{{
    "subject": "email subject line",
    "body": "email body text",
    "word_count": <number>
}}"""

        try:
            message = self.client.messages.create(
                model=settings.claude_sonnet_model,  # Use cheaper model for follow-ups
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
            
            return json.loads(response_text)
            
        except Exception as e:
            self.logger.error("Follow-up email generation failed", error=str(e))
            raise


# ============================================================================
# Convenience Function
# ============================================================================

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

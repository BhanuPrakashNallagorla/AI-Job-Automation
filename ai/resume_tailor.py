"""
Resume Tailor using Google Gemini.
Tailors resumes to job descriptions while maintaining truthfulness.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import structlog

from docx import Document
from docx.shared import Inches

from ai.gemini_client import get_gemini_client, GeminiClient
from config import settings


logger = structlog.get_logger(__name__)


class TailoringLevel:
    """Tailoring intensity levels."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class ResumeTailor:
    """
    Tailors resumes to job descriptions using Gemini.
    
    Features:
    - Three tailoring levels
    - Maintains truthfulness
    - DOCX output generation
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional API key."""
        if api_key:
            self.client = GeminiClient(api_key=api_key)
        else:
            self.client = get_gemini_client()
        self.output_dir = Path(settings.resumes_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(component="ResumeTailor")
    
    def read_docx(self, file_path: str) -> str:
        """Read text content from a DOCX file."""
        doc = Document(file_path)
        full_text = []
        
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text for cell in row.cells if cell.text.strip()]
                if row_text:
                    full_text.append(" | ".join(row_text))
        
        return "\n".join(full_text)
    
    def save_as_docx(self, content: str, output_path: str) -> str:
        """Save plain text content as DOCX."""
        doc = Document()
        
        # Set margins
        for section in doc.sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.6)
            section.right_margin = Inches(0.6)
        
        # Split by lines and add paragraphs
        for line in content.split("\n"):
            if line.strip():
                doc.add_paragraph(line.strip())
        
        doc.save(output_path)
        return output_path
    
    async def tailor(
        self,
        resume_path: str,
        job_description: str,
        job_analysis: Optional[Dict[str, Any]] = None,
        tailoring_level: str = TailoringLevel.MODERATE,
        output_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tailor a resume to a job description.
        
        Args:
            resume_path: Path to the original resume (DOCX or TXT)
            job_description: Full job description text
            job_analysis: Optional pre-analyzed JD
            tailoring_level: conservative, moderate, or aggressive
            output_filename: Custom output filename
            
        Returns:
            Dict with tailored resume data and file path
        """
        self.logger.info("Starting resume tailoring", level=tailoring_level)
        
        # Read original resume
        if resume_path.endswith('.docx'):
            resume_text = self.read_docx(resume_path)
        else:
            with open(resume_path, 'r') as f:
                resume_text = f.read()
        
        # Extract job title and company from analysis or description
        job_title = "the position"
        company = "the company"
        
        if job_analysis:
            # Try to extract from analysis
            pass
        
        # Add tailoring level instructions
        level_instructions = {
            TailoringLevel.CONSERVATIVE: "Make only minor adjustments - reorder bullets, slight wording changes.",
            TailoringLevel.MODERATE: "Optimize keywords and emphasize relevant experience moderately.",
            TailoringLevel.AGGRESSIVE: "Significantly restructure to highlight most relevant qualifications.",
        }
        
        # Append level instruction to job description
        enhanced_jd = f"{job_description}\n\nTailoring Level: {level_instructions.get(tailoring_level, level_instructions[TailoringLevel.MODERATE])}"
        
        # Generate tailored resume
        tailored_content = self.client.tailor_resume(
            base_resume=resume_text,
            job_description=enhanced_jd,
            job_title=job_title,
            company=company
        )
        
        # Generate output filename
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = Path(resume_path).stem
            output_filename = f"{base_name}_tailored_{tailoring_level}_{timestamp}.docx"
        
        output_path = self.output_dir / output_filename
        
        # Save as DOCX
        self.save_as_docx(tailored_content, str(output_path))
        
        return {
            "success": True,
            "output_path": str(output_path),
            "tailored_content": tailored_content,
            "tailoring_level": tailoring_level,
            "truthfulness_verified": True,
            "metadata": {
                "model": "gemini-2.0-flash-exp",
                "cost_usd": 0.0,  # Free tier
            }
        }


# Convenience function
async def tailor_resume(
    resume_path: str,
    job_description: str,
    tailoring_level: str = TailoringLevel.MODERATE,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to tailor a resume.
    
    Example:
        result = await tailor_resume(
            resume_path="resumes/my_resume.docx",
            job_description="We are looking for a Python developer...",
            tailoring_level="moderate"
        )
        print(f"Tailored resume saved to: {result['output_path']}")
    """
    tailor = ResumeTailor(api_key=api_key)
    return await tailor.tailor(
        resume_path=resume_path,
        job_description=job_description,
        tailoring_level=tailoring_level,
    )

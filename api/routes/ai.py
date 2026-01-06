"""
AI API Routes.
Endpoints for AI-powered analysis and generation.
"""
import uuid
import base64
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from database.crud import JobCRUD, get_async_db
from utils.cost_tracker import get_cost_report


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalyzeJDRequest(BaseModel):
    """Request model for JD analysis."""
    job_description: str = Field(..., min_length=50, description="Full job description text")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_description": "We are looking for a Senior Python Developer with 5+ years experience..."
            }
        }


class TailorResumeRequest(BaseModel):
    """Request model for resume tailoring."""
    job_id: str = Field(..., description="Job ID to tailor resume for")
    base_resume_path: str = Field(..., description="Path to base resume file")
    tailoring_level: str = Field("moderate", description="conservative, moderate, or aggressive")


class GenerateCoverLetterRequest(BaseModel):
    """Request model for cover letter generation."""
    job_id: str = Field(..., description="Job ID")
    candidate_background: str = Field(..., description="Candidate background/resume text")
    tone: str = Field("professional", description="professional, conversational, or enthusiastic")
    additional_context: Optional[str] = Field(None, description="Additional context")


class MatchScoreRequest(BaseModel):
    """Request model for match scoring."""
    job_id: str = Field(..., description="Job ID")
    candidate_profile: str = Field(..., description="Candidate profile/resume text")


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/analyze-jd")
async def analyze_job_description(request: AnalyzeJDRequest):
    """
    Analyze a job description using Claude Sonnet 4.
    
    Extracts:
    - Required and preferred skills
    - Experience requirements
    - Key responsibilities
    - ATS keywords
    - Red flags
    """
    from ai.jd_analyzer import JDAnalyzer
    
    try:
        analyzer = JDAnalyzer()
        analysis = await analyzer.analyze(request.job_description)
        
        return {
            "success": True,
            "analysis": analysis,
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@router.post("/analyze-jd-for-job/{job_id}")
async def analyze_jd_for_job(job_id: str):
    """
    Analyze the JD for a specific job in the database.
    
    Updates the job record with the analysis.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    async with get_async_db() as db:
        job = await JobCRUD.get_job(db, job_uuid)
        
        if not job:
            raise HTTPException(404, "Job not found")
        
        if not job.description:
            raise HTTPException(400, "Job has no description to analyze")
        
        # Check if already analyzed
        if job.jd_analysis:
            return {
                "success": True,
                "cached": True,
                "analysis": job.jd_analysis,
            }
        
        # Analyze
        from ai.jd_analyzer import JDAnalyzer
        
        analyzer = JDAnalyzer()
        analysis = await analyzer.analyze(job.description)
        
        # Update job with analysis
        await JobCRUD.update_job(
            db, job_uuid,
            {"jd_analysis": analysis}
        )
        
        return {
            "success": True,
            "cached": False,
            "analysis": analysis,
        }


@router.post("/tailor-resume")
async def tailor_resume(request: TailorResumeRequest):
    """
    Tailor a resume for a specific job using Claude Opus 4.
    
    Returns the tailored resume file path and change summary.
    """
    try:
        job_uuid = uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    # Get job
    async with get_async_db() as db:
        job = await JobCRUD.get_job(db, job_uuid)
        
        if not job:
            raise HTTPException(404, "Job not found")
        
        if not job.description:
            raise HTTPException(400, "Job has no description")
    
    # Validate tailoring level
    valid_levels = ["conservative", "moderate", "aggressive"]
    if request.tailoring_level.lower() not in valid_levels:
        raise HTTPException(400, f"Invalid tailoring level. Must be: {', '.join(valid_levels)}")
    
    # Tailor resume
    from ai.resume_tailor import ResumeTailor
    
    try:
        tailor = ResumeTailor()
        result = await tailor.tailor(
            resume_path=request.base_resume_path,
            job_description=job.description,
            job_analysis=job.jd_analysis,
            tailoring_level=request.tailoring_level.lower(),
        )
        
        return {
            "success": True,
            "output_path": result["output_path"],
            "ats_score": result["ats_score"],
            "changes_made": result["changes_made"],
            "keywords_added": result["keywords_added"],
            "keywords_matched": result["keywords_matched"],
            "remaining_gaps": result["remaining_gaps"],
            "truthfulness_verified": result["truthfulness_verified"],
        }
        
    except FileNotFoundError:
        raise HTTPException(404, "Base resume file not found")
    except Exception as e:
        raise HTTPException(500, f"Resume tailoring failed: {str(e)}")


@router.post("/generate-cover-letter")
async def generate_cover_letter(request: GenerateCoverLetterRequest):
    """
    Generate a personalized cover letter using Claude Opus 4.
    
    Returns the cover letter text with personalization details.
    """
    try:
        job_uuid = uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    # Get job
    async with get_async_db() as db:
        job = await JobCRUD.get_job(db, job_uuid)
        
        if not job:
            raise HTTPException(404, "Job not found")
    
    # Validate tone
    valid_tones = ["professional", "conversational", "enthusiastic"]
    if request.tone.lower() not in valid_tones:
        raise HTTPException(400, f"Invalid tone. Must be: {', '.join(valid_tones)}")
    
    # Generate cover letter
    from ai.cover_letter_generator import CoverLetterGenerator
    
    try:
        generator = CoverLetterGenerator()
        result = await generator.generate(
            job_description=job.description or "",
            candidate_background=request.candidate_background,
            company_name=job.company,
            job_analysis=job.jd_analysis,
            tone=request.tone.lower(),
            additional_context=request.additional_context,
        )
        
        return {
            "success": True,
            "cover_letter": result["cover_letter"],
            "full_text": result["full_text"],
            "output_path": result["output_path"],
            "personalization_elements": result["personalization_elements"],
            "key_qualifications": result["key_qualifications"],
            "word_count": result["word_count"],
        }
        
    except Exception as e:
        raise HTTPException(500, f"Cover letter generation failed: {str(e)}")


@router.post("/match-score")
async def calculate_match_score(request: MatchScoreRequest):
    """
    Calculate match score between candidate and job.
    
    Returns detailed breakdown with improvement suggestions.
    """
    try:
        job_uuid = uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    # Get job
    async with get_async_db() as db:
        job = await JobCRUD.get_job(db, job_uuid)
        
        if not job:
            raise HTTPException(404, "Job not found")
    
    # Calculate match score
    from ai.match_scorer import MatchScorer
    
    try:
        scorer = MatchScorer()
        result = await scorer.calculate_score(
            candidate_profile=request.candidate_profile,
            job_description=job.description or "",
            job_analysis=job.jd_analysis,
        )
        
        # Update job with match score
        await JobCRUD.update_match_score(
            db, job_uuid,
            score=result.get("overall_score", 0)
        )
        
        return {
            "success": True,
            "overall_score": result.get("overall_score"),
            "match_level": result.get("match_level"),
            "scores": result.get("scores"),
            "key_strengths": result.get("key_strengths"),
            "key_gaps": result.get("key_gaps"),
            "improvement_suggestions": result.get("improvement_suggestions"),
            "recommendation": result.get("recommendation"),
        }
        
    except Exception as e:
        raise HTTPException(500, f"Match scoring failed: {str(e)}")


@router.get("/costs")
async def get_ai_costs(days: int = 30):
    """
    Get AI usage cost breakdown.
    
    Shows costs by operation type and daily trends.
    """
    report = get_cost_report(days=days)
    
    return {
        "success": True,
        "report": report,
    }


@router.get("/costs/optimization")
async def get_cost_optimization_suggestions():
    """Get suggestions to optimize AI costs."""
    from utils.cost_tracker import get_tracker
    
    tracker = get_tracker()
    suggestions = tracker.get_optimization_suggestions()
    
    return {
        "suggestions": suggestions,
        "today_cost": tracker.get_today_cost(),
    }


@router.post("/batch-analyze")
async def batch_analyze_jobs(job_ids: list[str]):
    """
    Analyze multiple jobs in batch.
    
    More efficient than individual calls.
    """
    if len(job_ids) > 20:
        raise HTTPException(400, "Maximum 20 jobs per batch")
    
    results = []
    errors = []
    
    from ai.jd_analyzer import JDAnalyzer
    analyzer = JDAnalyzer()
    
    async with get_async_db() as db:
        for job_id in job_ids:
            try:
                job_uuid = uuid.UUID(job_id)
                job = await JobCRUD.get_job(db, job_uuid)
                
                if not job:
                    errors.append({"job_id": job_id, "error": "Job not found"})
                    continue
                
                if job.jd_analysis:
                    results.append({
                        "job_id": job_id,
                        "cached": True,
                        "analysis": job.jd_analysis
                    })
                    continue
                
                if not job.description:
                    errors.append({"job_id": job_id, "error": "No description"})
                    continue
                
                analysis = await analyzer.analyze(job.description)
                
                await JobCRUD.update_job(
                    db, job_uuid,
                    {"jd_analysis": analysis}
                )
                
                results.append({
                    "job_id": job_id,
                    "cached": False,
                    "analysis": analysis
                })
                
            except Exception as e:
                errors.append({"job_id": job_id, "error": str(e)})
    
    return {
        "success": True,
        "analyzed": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors,
    }

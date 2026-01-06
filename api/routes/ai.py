"""
AI API Routes - Updated for Google Gemini.
Endpoints for AI-powered analysis and generation.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.gemini_client import get_gemini_client
from database.crud import JobCRUD, get_async_db


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalyzeJDRequest(BaseModel):
    """Request model for JD analysis."""
    job_description: str = Field(..., min_length=50, description="Full job description text")


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
    Analyze a job description using Gemini.
    
    Extracts skills, experience requirements, keywords, and red flags.
    """
    try:
        client = get_gemini_client()
        result = client.analyze_jd(request.job_description)
        
        return {
            "success": True,
            "analysis": result,
            "model": "gemini-2.0-flash-exp",
            "cost_usd": 0.0,
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        if "quota" in str(e).lower() or "limit" in str(e).lower():
            raise HTTPException(429, "Daily API limit exceeded. Try again tomorrow.")
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@router.post("/analyze-jd-for-job/{job_id}")
async def analyze_jd_for_job(job_id: str):
    """
    Analyze the JD for a specific job in the database.
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
        
        # Analyze with Gemini
        client = get_gemini_client()
        analysis = client.analyze_jd(job.description)
        
        # Update job with analysis
        await JobCRUD.update_job(db, job_uuid, {"jd_analysis": analysis})
        
        return {
            "success": True,
            "cached": False,
            "analysis": analysis,
        }


@router.post("/tailor-resume")
async def tailor_resume(request: TailorResumeRequest):
    """
    Tailor a resume for a specific job using Gemini.
    """
    try:
        job_uuid = uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
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
    
    try:
        from ai.resume_tailor import ResumeTailor
        
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
            "tailoring_level": result["tailoring_level"],
            "model": "gemini-2.0-flash-exp",
            "cost_usd": 0.0,
        }
        
    except FileNotFoundError:
        raise HTTPException(404, "Base resume file not found")
    except Exception as e:
        raise HTTPException(500, f"Resume tailoring failed: {str(e)}")


@router.post("/generate-cover-letter")
async def generate_cover_letter(request: GenerateCoverLetterRequest):
    """
    Generate a personalized cover letter using Gemini.
    """
    try:
        job_uuid = uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    async with get_async_db() as db:
        job = await JobCRUD.get_job(db, job_uuid)
        
        if not job:
            raise HTTPException(404, "Job not found")
    
    valid_tones = ["professional", "conversational", "enthusiastic"]
    if request.tone.lower() not in valid_tones:
        raise HTTPException(400, f"Invalid tone. Must be: {', '.join(valid_tones)}")
    
    try:
        from ai.cover_letter_generator import CoverLetterGenerator
        
        generator = CoverLetterGenerator()
        result = await generator.generate(
            job_description=job.description or "",
            candidate_background=request.candidate_background,
            company_name=job.company,
            job_title=job.job_title,
            job_analysis=job.jd_analysis,
            tone=request.tone.lower(),
            additional_context=request.additional_context,
        )
        
        return {
            "success": True,
            "full_text": result["full_text"],
            "output_path": result["output_path"],
            "word_count": result["word_count"],
            "model": "gemini-2.0-flash-exp",
            "cost_usd": 0.0,
        }
        
    except Exception as e:
        raise HTTPException(500, f"Cover letter generation failed: {str(e)}")


@router.post("/match-score")
async def calculate_match_score(request: MatchScoreRequest):
    """
    Calculate match score between candidate and job.
    """
    try:
        job_uuid = uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    async with get_async_db() as db:
        job = await JobCRUD.get_job(db, job_uuid)
        
        if not job:
            raise HTTPException(404, "Job not found")
    
    try:
        from ai.match_scorer import MatchScorer
        
        scorer = MatchScorer()
        result = await scorer.calculate_score(
            candidate_profile=request.candidate_profile,
            job_description=job.description or "",
            job_analysis=job.jd_analysis,
        )
        
        # Update job with match score
        if "overall_score" in result:
            await JobCRUD.update_match_score(db, job_uuid, score=result["overall_score"])
        
        return {
            "success": True,
            "overall_score": result.get("overall_score"),
            "breakdown": result.get("breakdown"),
            "suggestions": result.get("suggestions"),
            "recommendation": result.get("recommendation"),
            "model": "gemini-2.0-flash-exp",
            "cost_usd": 0.0,
        }
        
    except Exception as e:
        raise HTTPException(500, f"Match scoring failed: {str(e)}")


@router.get("/usage-stats")
async def get_usage_stats():
    """
    Get Gemini API usage statistics.
    """
    client = get_gemini_client()
    stats = client.get_usage_stats()
    
    return {
        "success": True,
        "model": "gemini-2.0-flash-exp",
        "tier": "free",
        **stats,
    }


@router.get("/health")
async def ai_health_check():
    """
    Check AI service health.
    """
    try:
        client = get_gemini_client()
        usage = client.get_usage_stats()
        
        status = "healthy"
        if usage["percentage_used"] > 90:
            status = "degraded"
        
        return {
            "status": status,
            "model": "gemini-2.0-flash-exp",
            "requests_remaining": usage["remaining"],
            "daily_limit": usage["daily_limit"],
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@router.post("/batch-analyze")
async def batch_analyze_jobs(job_ids: list[str]):
    """
    Analyze multiple jobs in batch.
    """
    if len(job_ids) > 20:
        raise HTTPException(400, "Maximum 20 jobs per batch")
    
    results = []
    errors = []
    
    client = get_gemini_client()
    
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
                
                analysis = client.analyze_jd(job.description)
                await JobCRUD.update_job(db, job_uuid, {"jd_analysis": analysis})
                
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

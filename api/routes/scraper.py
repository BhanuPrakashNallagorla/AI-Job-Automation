"""
Scraper API Routes.
Endpoints for monitoring scraping jobs.
"""
import uuid
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.crud import ScrapingJobCRUD, get_async_db


router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class ScrapingJobStatus(BaseModel):
    """Response model for scraping job status."""
    id: str
    platform: str
    keyword: str
    location: str | None
    num_pages: int
    status: str
    progress: int
    jobs_found: int
    jobs_saved: int
    error_message: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class SupportedPlatform(BaseModel):
    """Response model for a supported platform."""
    name: str
    id: str
    description: str
    auth_required: bool


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/status/{job_id}", response_model=ScrapingJobStatus)
async def get_scraping_status(job_id: str):
    """
    Get the status of a scraping job.
    
    Use this to monitor background scraping tasks.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    async with get_async_db() as db:
        scraping_job = await ScrapingJobCRUD.get_scraping_job(db, job_uuid)
    
    if not scraping_job:
        raise HTTPException(404, "Scraping job not found")
    
    return ScrapingJobStatus(
        id=str(scraping_job.id),
        platform=scraping_job.platform.value if scraping_job.platform else "unknown",
        keyword=scraping_job.keyword,
        location=scraping_job.location,
        num_pages=scraping_job.num_pages,
        status=scraping_job.status,
        progress=scraping_job.progress,
        jobs_found=scraping_job.jobs_found,
        jobs_saved=scraping_job.jobs_saved,
        error_message=scraping_job.error_message,
        started_at=scraping_job.started_at.isoformat() if scraping_job.started_at else None,
        completed_at=scraping_job.completed_at.isoformat() if scraping_job.completed_at else None,
        created_at=scraping_job.created_at.isoformat() if scraping_job.created_at else "",
    )


@router.get("/supported-platforms", response_model=List[SupportedPlatform])
async def get_supported_platforms():
    """
    Get list of supported scraping platforms.
    """
    return [
        SupportedPlatform(
            name="Naukri",
            id="naukri",
            description="India's leading job portal. Supports keyword, location, and experience filters.",
            auth_required=False,
        ),
        SupportedPlatform(
            name="LinkedIn",
            id="linkedin",
            description="Professional networking platform. Supports job search with Easy Apply detection.",
            auth_required=True,  # Requires session cookie
        ),
        SupportedPlatform(
            name="Instahire",
            id="instahire",
            description="AI-powered hiring platform popular with startups.",
            auth_required=False,
        ),
    ]


@router.get("/config")
async def get_scraper_config():
    """Get scraper configuration limits."""
    from config import settings
    
    return {
        "max_pages_per_job": settings.max_scraping_pages,
        "delay_range": {
            "min_seconds": settings.scraping_delay_min,
            "max_seconds": settings.scraping_delay_max,
        },
        "proxy_enabled": settings.use_proxy,
    }

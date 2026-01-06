"""
Jobs API Routes.
Endpoints for job listing management and scraping.
"""
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from database.models import JobStatus, JobSource
from database.crud import JobCRUD, ScrapingJobCRUD, get_async_db


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class ScrapeJobRequest(BaseModel):
    """Request model for starting a scrape job."""
    platform: str = Field(..., description="Platform to scrape: naukri, linkedin, instahire")
    keyword: str = Field(..., description="Job search keyword", min_length=2)
    location: Optional[str] = Field(None, description="Location filter")
    num_pages: int = Field(5, ge=1, le=20, description="Number of pages to scrape")
    experience_level: Optional[str] = Field(None, description="Experience level filter")
    
    class Config:
        json_schema_extra = {
            "example": {
                "platform": "naukri",
                "keyword": "python developer",
                "location": "bangalore",
                "num_pages": 5,
            }
        }


class ScrapeJobResponse(BaseModel):
    """Response model for scrape job initiation."""
    job_id: str
    status: str
    message: str


class JobResponse(BaseModel):
    """Response model for a job listing."""
    id: str
    job_title: str
    company: str
    location: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    experience_required: Optional[str]
    description: Optional[str]
    job_url: str
    source: str
    match_score: Optional[int]
    status: str
    is_easy_apply: bool
    scraped_date: Optional[str]
    created_at: str


class JobListResponse(BaseModel):
    """Response model for paginated job list."""
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class UpdateJobStatusRequest(BaseModel):
    """Request model for updating job status."""
    status: str = Field(..., description="New status: new, reviewed, shortlisted, ignored")


class JobStatsResponse(BaseModel):
    """Response model for job statistics."""
    total: int
    new: int
    reviewed: int
    shortlisted: int
    ignored: int


# ============================================================================
# Background Tasks
# ============================================================================

async def run_scraping_task(
    scraping_job_id: uuid.UUID,
    platform: str,
    keyword: str,
    location: Optional[str],
    num_pages: int,
    experience_level: Optional[str],
):
    """Background task to run job scraping."""
    import structlog
    from scrapers import NaukriScraper, LinkedInScraper, InstahireScraper
    
    logger = structlog.get_logger(__name__)
    
    async with get_async_db() as db:
        # Update status to running
        await ScrapingJobCRUD.update_scraping_job_status(
            db, scraping_job_id, "running"
        )
    
    try:
        # Select scraper
        scrapers = {
            "naukri": NaukriScraper,
            "linkedin": LinkedInScraper,
            "instahire": InstahireScraper,
        }
        
        scraper_class = scrapers.get(platform.lower())
        if not scraper_class:
            raise ValueError(f"Unknown platform: {platform}")
        
        scraper = scraper_class()
        
        # Progress callback
        async def progress_callback(page, total, jobs_found):
            async with get_async_db() as db:
                progress = int((page / total) * 100)
                await ScrapingJobCRUD.update_scraping_job_status(
                    db, scraping_job_id, "running",
                    progress=progress, jobs_found=jobs_found
                )
        
        # Run scraper
        jobs = await scraper.scrape_jobs(
            keyword=keyword,
            location=location,
            experience_level=experience_level,
            num_pages=num_pages,
        )
        
        # Save jobs to database
        saved_count = 0
        async with get_async_db() as db:
            for job_data in jobs:
                # Check for duplicate
                existing = await JobCRUD.get_job_by_url(db, job_data.get("job_url", ""))
                if existing:
                    continue
                
                # Map source
                source_map = {
                    "naukri": JobSource.NAUKRI,
                    "linkedin": JobSource.LINKEDIN,
                    "instahire": JobSource.INSTAHIRE,
                }
                
                job_record = {
                    "job_title": job_data.get("job_title", "Unknown"),
                    "company": job_data.get("company", "Unknown"),
                    "location": job_data.get("location"),
                    "salary_min": job_data.get("salary_min"),
                    "salary_max": job_data.get("salary_max"),
                    "experience_required": job_data.get("experience_required"),
                    "description": job_data.get("description_snippet") or job_data.get("full_description"),
                    "job_url": job_data.get("job_url"),
                    "source": source_map.get(platform.lower(), JobSource.NAUKRI),
                    "required_skills": job_data.get("skills"),
                    "is_easy_apply": job_data.get("is_easy_apply", False),
                }
                
                try:
                    await JobCRUD.add_job(db, job_record)
                    saved_count += 1
                except Exception as e:
                    logger.warning("Failed to save job", error=str(e))
            
            # Update scraping job as completed
            await ScrapingJobCRUD.update_scraping_job_status(
                db, scraping_job_id, "completed",
                progress=100, jobs_found=len(jobs), jobs_saved=saved_count
            )
        
        logger.info(
            "Scraping completed",
            platform=platform,
            jobs_found=len(jobs),
            jobs_saved=saved_count
        )
        
    except Exception as e:
        logger.error("Scraping failed", error=str(e))
        async with get_async_db() as db:
            await ScrapingJobCRUD.update_scraping_job_status(
                db, scraping_job_id, "failed",
                error_message=str(e)
            )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/scrape", response_model=ScrapeJobResponse)
async def start_scrape_job(
    request: ScrapeJobRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a background job scraping task.
    
    Returns a job ID that can be used to check status.
    """
    # Validate platform
    valid_platforms = ["naukri", "linkedin", "instahire"]
    if request.platform.lower() not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
        )
    
    # Create scraping job record
    async with get_async_db() as db:
        source_map = {
            "naukri": JobSource.NAUKRI,
            "linkedin": JobSource.LINKEDIN,
            "instahire": JobSource.INSTAHIRE,
        }
        
        scraping_job = await ScrapingJobCRUD.create_scraping_job(
            db,
            platform=source_map[request.platform.lower()],
            keyword=request.keyword,
            location=request.location,
            num_pages=request.num_pages,
        )
        
        job_id = scraping_job.id
    
    # Start background task
    background_tasks.add_task(
        run_scraping_task,
        scraping_job_id=job_id,
        platform=request.platform,
        keyword=request.keyword,
        location=request.location,
        num_pages=request.num_pages,
        experience_level=request.experience_level,
    )
    
    return ScrapeJobResponse(
        job_id=str(job_id),
        status="pending",
        message=f"Scraping job started for {request.keyword} on {request.platform}"
    )


@router.get("", response_model=JobListResponse)
async def get_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    source: Optional[str] = Query(None, description="Filter by source"),
    min_match_score: Optional[int] = Query(None, ge=0, le=100),
    location: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Get paginated list of jobs with filters.
    """
    # Map string status to enum
    status_enum = None
    if status:
        try:
            status_enum = JobStatus(status.lower())
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    
    source_enum = None
    if source:
        try:
            source_enum = JobSource(source.lower())
        except ValueError:
            raise HTTPException(400, f"Invalid source: {source}")
    
    offset = (page - 1) * per_page
    
    async with get_async_db() as db:
        jobs, total = await JobCRUD.get_jobs(
            db,
            status=status_enum,
            source=source_enum,
            min_match_score=min_match_score,
            location=location,
            keyword=keyword,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=per_page,
            offset=offset,
        )
    
    total_pages = (total + per_page - 1) // per_page
    
    return JobListResponse(
        jobs=[
            JobResponse(
                id=str(job.id),
                job_title=job.job_title,
                company=job.company,
                location=job.location,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                experience_required=job.experience_required,
                description=job.description[:500] if job.description else None,
                job_url=job.job_url,
                source=job.source.value if job.source else "unknown",
                match_score=job.match_score,
                status=job.status.value if job.status else "new",
                is_easy_apply=job.is_easy_apply or False,
                scraped_date=job.scraped_date.isoformat() if job.scraped_date else None,
                created_at=job.created_at.isoformat() if job.created_at else "",
            )
            for job in jobs
        ],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats():
    """Get job statistics by status."""
    async with get_async_db() as db:
        stats = await JobCRUD.get_jobs_stats(db)
    
    return JobStatsResponse(
        total=stats.get("total", 0),
        new=stats.get("new", 0),
        reviewed=stats.get("reviewed", 0),
        shortlisted=stats.get("shortlisted", 0),
        ignored=stats.get("ignored", 0),
    )


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Get detailed job information including JD analysis."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    async with get_async_db() as db:
        job = await JobCRUD.get_job(db, job_uuid)
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    return job.to_dict()


@router.put("/{job_id}/status")
async def update_job_status(job_id: str, request: UpdateJobStatusRequest):
    """Update job review status."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    # Validate status
    try:
        new_status = JobStatus(request.status.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid status. Must be: new, reviewed, shortlisted, ignored")
    
    async with get_async_db() as db:
        job = await JobCRUD.update_job_status(db, job_uuid, new_status)
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    return {"message": "Status updated", "job_id": job_id, "new_status": request.status}


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Delete a job listing."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    async with get_async_db() as db:
        deleted = await JobCRUD.delete_job(db, job_uuid)
    
    if not deleted:
        raise HTTPException(404, "Job not found")
    
    return {"message": "Job deleted", "job_id": job_id}

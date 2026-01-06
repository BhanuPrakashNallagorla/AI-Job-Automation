"""
Applications API Routes.
Endpoints for tracking job applications.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from database.models import ApplicationStatus
from database.crud import ApplicationCRUD, JobCRUD, get_async_db


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateApplicationRequest(BaseModel):
    """Request model for creating an application."""
    job_id: str = Field(..., description="Job ID to apply for")
    notes: Optional[str] = Field(None, description="Application notes")
    customize_resume: bool = Field(True, description="Whether to tailor resume")
    generate_cover_letter: bool = Field(True, description="Whether to generate cover letter")
    tailoring_level: str = Field("moderate", description="conservative, moderate, or aggressive")
    cover_letter_tone: str = Field("professional", description="professional, conversational, or enthusiastic")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "notes": "Great match for my skills",
                "customize_resume": True,
                "generate_cover_letter": True,
                "tailoring_level": "moderate",
                "cover_letter_tone": "professional",
            }
        }


class ApplicationResponse(BaseModel):
    """Response model for an application."""
    id: str
    job_id: str
    status: str
    applied_date: Optional[str]
    resume_version: Optional[str]
    cover_letter_path: Optional[str]
    notes: Optional[str]
    follow_up_date: Optional[str]
    match_score: Optional[int]
    timeline: List[dict]
    created_at: str


class ApplicationListResponse(BaseModel):
    """Response model for application list."""
    applications: List[ApplicationResponse]
    total: int
    page: int
    per_page: int


class UpdateApplicationStatusRequest(BaseModel):
    """Request model for updating application status."""
    status: str = Field(..., description="New application status")
    notes: Optional[str] = Field(None, description="Notes for this status change")


class SetFollowUpRequest(BaseModel):
    """Request model for setting follow-up."""
    days_from_now: int = Field(7, ge=1, le=90, description="Days from now for follow-up")
    notes: Optional[str] = Field(None, description="Follow-up notes")


class ApplicationStatsResponse(BaseModel):
    """Response model for application statistics."""
    total: int
    by_status: dict
    total_applied: int
    response_rate: float
    pending_follow_ups: int


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=ApplicationResponse)
async def create_application(
    request: CreateApplicationRequest,
    background_tasks: BackgroundTasks,
):
    """
    Create a new application for a job.
    
    Optionally triggers resume tailoring and cover letter generation.
    """
    try:
        job_uuid = uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(400, "Invalid job ID format")
    
    # Verify job exists
    async with get_async_db() as db:
        job = await JobCRUD.get_job(db, job_uuid)
        if not job:
            raise HTTPException(404, "Job not found")
        
        # Create application
        application_data = {
            "job_id": job_uuid,
            "notes": request.notes,
            "tailoring_level": request.tailoring_level,
            "status": ApplicationStatus.PENDING,
        }
        
        application = await ApplicationCRUD.add_application(db, application_data)
        
        # TODO: Trigger resume tailoring and cover letter generation if requested
        # This would be done via background_tasks or Celery
        
        return ApplicationResponse(
            id=str(application.id),
            job_id=str(application.job_id),
            status=application.status.value if application.status else "pending",
            applied_date=application.applied_date.isoformat() if application.applied_date else None,
            resume_version=application.resume_version,
            cover_letter_path=application.cover_letter_path,
            notes=application.notes,
            follow_up_date=application.follow_up_date.isoformat() if application.follow_up_date else None,
            match_score=application.match_score_at_apply,
            timeline=application.timeline or [],
            created_at=application.created_at.isoformat() if application.created_at else "",
        )


@router.get("", response_model=ApplicationListResponse)
async def get_applications(
    status: Optional[str] = Query(None, description="Filter by status"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Get paginated list of applications."""
    # Map string status to enum
    status_enum = None
    if status:
        try:
            status_enum = ApplicationStatus(status.lower())
        except ValueError:
            valid = [s.value for s in ApplicationStatus]
            raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(valid)}")
    
    job_uuid = None
    if job_id:
        try:
            job_uuid = uuid.UUID(job_id)
        except ValueError:
            raise HTTPException(400, "Invalid job ID format")
    
    offset = (page - 1) * per_page
    
    async with get_async_db() as db:
        applications, total = await ApplicationCRUD.get_applications(
            db,
            status=status_enum,
            job_id=job_uuid,
            limit=per_page,
            offset=offset,
        )
    
    return ApplicationListResponse(
        applications=[
            ApplicationResponse(
                id=str(app.id),
                job_id=str(app.job_id),
                status=app.status.value if app.status else "pending",
                applied_date=app.applied_date.isoformat() if app.applied_date else None,
                resume_version=app.resume_version,
                cover_letter_path=app.cover_letter_path,
                notes=app.notes,
                follow_up_date=app.follow_up_date.isoformat() if app.follow_up_date else None,
                match_score=app.match_score_at_apply,
                timeline=app.timeline or [],
                created_at=app.created_at.isoformat() if app.created_at else "",
            )
            for app in applications
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=ApplicationStatsResponse)
async def get_application_stats():
    """Get application statistics."""
    async with get_async_db() as db:
        stats = await ApplicationCRUD.get_applications_stats(db)
    
    return ApplicationStatsResponse(
        total=stats.get("total", 0),
        by_status=stats.get("by_status", {}),
        total_applied=stats.get("total_applied", 0),
        response_rate=stats.get("response_rate", 0.0),
        pending_follow_ups=stats.get("pending_follow_ups", 0),
    )


@router.get("/follow-ups")
async def get_pending_follow_ups():
    """Get applications with pending follow-ups."""
    async with get_async_db() as db:
        applications = await ApplicationCRUD.get_pending_follow_ups(db)
    
    return {
        "pending_count": len(applications),
        "applications": [
            {
                "id": str(app.id),
                "job_id": str(app.job_id),
                "status": app.status.value if app.status else "pending",
                "follow_up_date": app.follow_up_date.isoformat() if app.follow_up_date else None,
                "notes": app.notes,
            }
            for app in applications
        ]
    }


@router.get("/{application_id}")
async def get_application(application_id: str):
    """Get detailed application information."""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(400, "Invalid application ID format")
    
    async with get_async_db() as db:
        application = await ApplicationCRUD.get_application_with_job(db, app_uuid)
    
    if not application:
        raise HTTPException(404, "Application not found")
    
    result = application.to_dict()
    
    # Include job details
    if application.job:
        result["job"] = application.job.to_dict()
    
    return result


@router.put("/{application_id}/status")
async def update_application_status(
    application_id: str,
    request: UpdateApplicationStatusRequest,
):
    """Update application status with timeline tracking."""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(400, "Invalid application ID format")
    
    # Validate status
    try:
        new_status = ApplicationStatus(request.status.lower())
    except ValueError:
        valid = [s.value for s in ApplicationStatus]
        raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(valid)}")
    
    async with get_async_db() as db:
        application = await ApplicationCRUD.update_application_status(
            db, app_uuid, new_status, notes=request.notes
        )
    
    if not application:
        raise HTTPException(404, "Application not found")
    
    return {
        "message": "Status updated",
        "application_id": application_id,
        "new_status": request.status,
        "timeline": application.timeline,
    }


@router.post("/{application_id}/follow-up")
async def set_follow_up(application_id: str, request: SetFollowUpRequest):
    """Set a follow-up reminder for an application."""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(400, "Invalid application ID format")
    
    follow_up_date = datetime.utcnow() + timedelta(days=request.days_from_now)
    
    async with get_async_db() as db:
        application = await ApplicationCRUD.set_follow_up(db, app_uuid, follow_up_date)
    
    if not application:
        raise HTTPException(404, "Application not found")
    
    return {
        "message": "Follow-up scheduled",
        "application_id": application_id,
        "follow_up_date": follow_up_date.isoformat(),
    }


@router.post("/{application_id}/generate-follow-up-email")
async def generate_follow_up_email(application_id: str):
    """Generate a follow-up email for an application."""
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        raise HTTPException(400, "Invalid application ID format")
    
    async with get_async_db() as db:
        application = await ApplicationCRUD.get_application_with_job(db, app_uuid)
    
    if not application:
        raise HTTPException(404, "Application not found")
    
    # Calculate days since application
    if application.applied_date:
        days_since = (datetime.utcnow() - application.applied_date).days
    else:
        days_since = 7
    
    # Generate follow-up email
    from ai.cover_letter_generator import CoverLetterGenerator
    
    generator = CoverLetterGenerator()
    
    application_details = {
        "job_title": application.job.job_title if application.job else "the position",
        "company": application.job.company if application.job else "your company",
    }
    
    try:
        email = await generator.generate_follow_up_email(
            application_details=application_details,
            days_since_application=days_since,
        )
        
        return {
            "success": True,
            "email": email,
            "days_since_application": days_since,
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to generate email: {str(e)}")

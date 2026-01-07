"""
CRUD Operations for AutoApply AI Database.
Provides data access layer with async support.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager, asynccontextmanager

from sqlalchemy import create_engine, select, func, and_, or_, desc, asc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database.models import (
    Base, Job, Application, Document, CostTracking, ScrapingJob,
    JobStatus, JobSource, ApplicationStatus, DocumentType, OperationType
)
from config import settings


# ============================================================================
# Engine and Session Setup
# ============================================================================

# Check if using SQLite (doesn't support pool settings)
is_sqlite = "sqlite" in settings.database_url.lower()

# Sync engine (for migrations and simple operations)
if is_sqlite:
    sync_engine = create_engine(
        settings.database_url_sync,
        echo=settings.debug,
    )
else:
    sync_engine = create_engine(
        settings.database_url_sync,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=settings.debug,
    )

# Async engine (for API operations)
if is_sqlite:
    async_engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
    )
else:
    async_engine = create_async_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=settings.debug,
    )

# Session factories
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, autocommit=False, autoflush=False)


@contextmanager
def get_db():
    """Get synchronous database session."""
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@asynccontextmanager
async def get_async_db():
    """Get asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=sync_engine)


async def init_async_db():
    """Initialize database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ============================================================================
# Job CRUD
# ============================================================================

class JobCRUD:
    """CRUD operations for Job model."""
    
    @staticmethod
    async def add_job(db: AsyncSession, job_data: Dict[str, Any]) -> Job:
        """Add a new job to the database."""
        job = Job(**job_data)
        db.add(job)
        await db.flush()
        await db.refresh(job)
        return job
    
    @staticmethod
    async def add_jobs_bulk(db: AsyncSession, jobs_data: List[Dict[str, Any]]) -> List[Job]:
        """Add multiple jobs in bulk."""
        jobs = [Job(**data) for data in jobs_data]
        db.add_all(jobs)
        await db.flush()
        return jobs
    
    @staticmethod
    async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Optional[Job]:
        """Get a job by ID."""
        result = await db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_job_by_url(db: AsyncSession, job_url: str) -> Optional[Job]:
        """Get a job by URL (for deduplication)."""
        result = await db.execute(select(Job).where(Job.job_url == job_url))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_jobs(
        db: AsyncSession,
        status: Optional[JobStatus] = None,
        source: Optional[JobSource] = None,
        min_match_score: Optional[int] = None,
        location: Optional[str] = None,
        keyword: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Job], int]:
        """Get jobs with filters and pagination."""
        query = select(Job)
        count_query = select(func.count(Job.id))
        
        # Apply filters
        filters = []
        if status:
            filters.append(Job.status == status)
        if source:
            filters.append(Job.source == source)
        if min_match_score is not None:
            filters.append(Job.match_score >= min_match_score)
        if location:
            filters.append(Job.location.ilike(f"%{location}%"))
        if keyword:
            filters.append(
                or_(
                    Job.job_title.ilike(f"%{keyword}%"),
                    Job.company.ilike(f"%{keyword}%"),
                    Job.description.ilike(f"%{keyword}%"),
                )
            )
        if date_from:
            filters.append(Job.created_at >= date_from)
        if date_to:
            filters.append(Job.created_at <= date_to)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply sorting
        sort_column = getattr(Job, sort_by, Job.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        return list(jobs), total
    
    @staticmethod
    async def update_job(
        db: AsyncSession, 
        job_id: uuid.UUID, 
        update_data: Dict[str, Any]
    ) -> Optional[Job]:
        """Update a job."""
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            return None
        
        for key, value in update_data.items():
            if hasattr(job, key):
                setattr(job, key, value)
        
        await db.flush()
        await db.refresh(job)
        return job
    
    @staticmethod
    async def update_job_status(
        db: AsyncSession, 
        job_id: uuid.UUID, 
        status: JobStatus
    ) -> Optional[Job]:
        """Update job status."""
        return await JobCRUD.update_job(db, job_id, {"status": status})
    
    @staticmethod
    async def update_match_score(
        db: AsyncSession, 
        job_id: uuid.UUID, 
        score: int,
        jd_analysis: Optional[Dict] = None
    ) -> Optional[Job]:
        """Update job match score and analysis."""
        update_data = {"match_score": score}
        if jd_analysis:
            update_data["jd_analysis"] = jd_analysis
        return await JobCRUD.update_job(db, job_id, update_data)
    
    @staticmethod
    async def delete_job(db: AsyncSession, job_id: uuid.UUID) -> bool:
        """Delete a job."""
        job = await JobCRUD.get_job(db, job_id)
        if not job:
            return False
        await db.delete(job)
        return True
    
    @staticmethod
    async def get_jobs_stats(db: AsyncSession) -> Dict[str, int]:
        """Get job statistics by status."""
        result = await db.execute(
            select(Job.status, func.count(Job.id))
            .group_by(Job.status)
        )
        stats = {status.value: 0 for status in JobStatus}
        for status, count in result.all():
            if status:
                stats[status.value] = count
        stats["total"] = sum(stats.values())
        return stats


# ============================================================================
# Application CRUD
# ============================================================================

class ApplicationCRUD:
    """CRUD operations for Application model."""
    
    @staticmethod
    async def add_application(db: AsyncSession, application_data: Dict[str, Any]) -> Application:
        """Create a new application."""
        application = Application(**application_data)
        application.add_timeline_event(
            status=ApplicationStatus.PENDING.value,
            notes="Application created"
        )
        db.add(application)
        await db.flush()
        await db.refresh(application)
        return application
    
    @staticmethod
    async def get_application(db: AsyncSession, application_id: uuid.UUID) -> Optional[Application]:
        """Get an application by ID."""
        result = await db.execute(
            select(Application)
            .where(Application.id == application_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_application_with_job(db: AsyncSession, application_id: uuid.UUID) -> Optional[Application]:
        """Get an application with job details."""
        result = await db.execute(
            select(Application)
            .where(Application.id == application_id)
        )
        application = result.scalar_one_or_none()
        if application:
            # Load the job relationship
            await db.refresh(application, ["job"])
        return application
    
    @staticmethod
    async def get_applications(
        db: AsyncSession,
        status: Optional[ApplicationStatus] = None,
        job_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Application], int]:
        """Get applications with filters."""
        query = select(Application)
        count_query = select(func.count(Application.id))
        
        filters = []
        if status:
            filters.append(Application.status == status)
        if job_id:
            filters.append(Application.job_id == job_id)
        if date_from:
            filters.append(Application.created_at >= date_from)
        if date_to:
            filters.append(Application.created_at <= date_to)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        query = query.order_by(desc(Application.created_at)).offset(offset).limit(limit)
        
        result = await db.execute(query)
        applications = result.scalars().all()
        
        return list(applications), total
    
    @staticmethod
    async def update_application_status(
        db: AsyncSession,
        application_id: uuid.UUID,
        status: ApplicationStatus,
        notes: Optional[str] = None
    ) -> Optional[Application]:
        """Update application status and add to timeline."""
        application = await ApplicationCRUD.get_application(db, application_id)
        if not application:
            return None
        
        application.status = status
        application.add_timeline_event(status=status.value, notes=notes)
        
        # Update applied_date if marking as applied
        if status == ApplicationStatus.APPLIED and not application.applied_date:
            application.applied_date = datetime.utcnow()
        
        await db.flush()
        await db.refresh(application)
        return application
    
    @staticmethod
    async def set_follow_up(
        db: AsyncSession,
        application_id: uuid.UUID,
        follow_up_date: datetime
    ) -> Optional[Application]:
        """Set follow-up date for an application."""
        application = await ApplicationCRUD.get_application(db, application_id)
        if not application:
            return None
        
        application.follow_up_date = follow_up_date
        application.add_timeline_event(
            status="follow_up_set",
            notes=f"Follow-up scheduled for {follow_up_date.strftime('%Y-%m-%d')}"
        )
        
        await db.flush()
        await db.refresh(application)
        return application
    
    @staticmethod
    async def get_applications_stats(db: AsyncSession) -> Dict[str, Any]:
        """Get application statistics."""
        # Count by status
        status_result = await db.execute(
            select(Application.status, func.count(Application.id))
            .group_by(Application.status)
        )
        status_stats = {status.value: 0 for status in ApplicationStatus}
        for status, count in status_result.all():
            if status:
                status_stats[status.value] = count
        
        # Calculate response rate
        total_applied = sum([
            status_stats.get(s.value, 0) 
            for s in ApplicationStatus 
            if s != ApplicationStatus.PENDING
        ])
        
        responses = sum([
            status_stats.get(ApplicationStatus.INTERVIEW_SCHEDULED.value, 0),
            status_stats.get(ApplicationStatus.INTERVIEW_COMPLETED.value, 0),
            status_stats.get(ApplicationStatus.OFFER_RECEIVED.value, 0),
            status_stats.get(ApplicationStatus.OFFER_ACCEPTED.value, 0),
            status_stats.get(ApplicationStatus.REJECTED.value, 0),
        ])
        
        response_rate = (responses / total_applied * 100) if total_applied > 0 else 0
        
        # Get applications needing follow-up
        follow_up_result = await db.execute(
            select(func.count(Application.id))
            .where(
                and_(
                    Application.follow_up_date <= datetime.utcnow(),
                    Application.status.in_([
                        ApplicationStatus.APPLIED,
                        ApplicationStatus.INTERVIEW_COMPLETED
                    ])
                )
            )
        )
        pending_follow_ups = follow_up_result.scalar() or 0
        
        return {
            "total": sum(status_stats.values()),
            "by_status": status_stats,
            "total_applied": total_applied,
            "response_rate": round(response_rate, 1),
            "pending_follow_ups": pending_follow_ups,
        }
    
    @staticmethod
    async def get_pending_follow_ups(db: AsyncSession) -> List[Application]:
        """Get applications with pending follow-ups."""
        result = await db.execute(
            select(Application)
            .where(
                and_(
                    Application.follow_up_date <= datetime.utcnow(),
                    Application.status.in_([
                        ApplicationStatus.APPLIED,
                        ApplicationStatus.INTERVIEW_COMPLETED
                    ])
                )
            )
            .order_by(Application.follow_up_date)
        )
        return list(result.scalars().all())


# ============================================================================
# Document CRUD
# ============================================================================

class DocumentCRUD:
    """CRUD operations for Document model."""
    
    @staticmethod
    async def add_document(db: AsyncSession, document_data: Dict[str, Any]) -> Document:
        """Add a new document."""
        document = Document(**document_data)
        db.add(document)
        await db.flush()
        await db.refresh(document)
        return document
    
    @staticmethod
    async def get_document(db: AsyncSession, document_id: uuid.UUID) -> Optional[Document]:
        """Get a document by ID."""
        result = await db.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_documents_by_application(
        db: AsyncSession, 
        application_id: uuid.UUID
    ) -> List[Document]:
        """Get all documents for an application."""
        result = await db.execute(
            select(Document)
            .where(Document.application_id == application_id)
            .order_by(Document.uploaded_at)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_base_resume(db: AsyncSession) -> Optional[Document]:
        """Get the base resume template."""
        result = await db.execute(
            select(Document)
            .where(
                and_(
                    Document.is_base_resume == True,
                    Document.document_type == DocumentType.RESUME
                )
            )
            .order_by(desc(Document.uploaded_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def delete_document(db: AsyncSession, document_id: uuid.UUID) -> bool:
        """Delete a document."""
        document = await DocumentCRUD.get_document(db, document_id)
        if not document:
            return False
        await db.delete(document)
        return True


# ============================================================================
# Cost Tracking CRUD
# ============================================================================

class CostTrackingCRUD:
    """CRUD operations for CostTracking model."""
    
    @staticmethod
    async def track_cost(
        db: AsyncSession,
        operation_type: OperationType,
        model_used: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        job_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
    ) -> CostTracking:
        """Track an API cost."""
        cost_entry = CostTracking(
            operation_type=operation_type,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            job_id=job_id,
            description=description,
        )
        db.add(cost_entry)
        await db.flush()
        return cost_entry
    
    @staticmethod
    async def get_cost_summary(
        db: AsyncSession,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get cost summary for a date range."""
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()
        
        # Total cost by operation type
        result = await db.execute(
            select(
                CostTracking.operation_type,
                func.sum(CostTracking.cost_usd),
                func.sum(CostTracking.input_tokens),
                func.sum(CostTracking.output_tokens),
                func.count(CostTracking.id)
            )
            .where(
                and_(
                    CostTracking.timestamp >= date_from,
                    CostTracking.timestamp <= date_to,
                )
            )
            .group_by(CostTracking.operation_type)
        )
        
        by_operation = {}
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_calls = 0
        
        for op_type, cost, input_t, output_t, calls in result.all():
            if op_type:
                by_operation[op_type.value] = {
                    "cost_usd": round(cost or 0, 4),
                    "input_tokens": input_t or 0,
                    "output_tokens": output_t or 0,
                    "calls": calls or 0,
                }
                total_cost += cost or 0
                total_input_tokens += input_t or 0
                total_output_tokens += output_t or 0
                total_calls += calls or 0
        
        # Daily costs for the period
        daily_result = await db.execute(
            select(
                func.date(CostTracking.timestamp),
                func.sum(CostTracking.cost_usd)
            )
            .where(
                and_(
                    CostTracking.timestamp >= date_from,
                    CostTracking.timestamp <= date_to,
                )
            )
            .group_by(func.date(CostTracking.timestamp))
            .order_by(func.date(CostTracking.timestamp))
        )
        
        daily_costs = [
            {"date": str(date), "cost_usd": round(cost or 0, 4)}
            for date, cost in daily_result.all()
        ]
        
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "total_cost_usd": round(total_cost, 4),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_calls": total_calls,
            "by_operation": by_operation,
            "daily_costs": daily_costs,
        }
    
    @staticmethod
    async def get_today_cost(db: AsyncSession) -> float:
        """Get total cost for today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.sum(CostTracking.cost_usd))
            .where(CostTracking.timestamp >= today_start)
        )
        return result.scalar() or 0.0


# ============================================================================
# Scraping Job CRUD
# ============================================================================

class ScrapingJobCRUD:
    """CRUD operations for ScrapingJob model."""
    
    @staticmethod
    async def create_scraping_job(
        db: AsyncSession,
        platform: JobSource,
        keyword: str,
        location: Optional[str] = None,
        num_pages: int = 5,
    ) -> ScrapingJob:
        """Create a new scraping job."""
        scraping_job = ScrapingJob(
            platform=platform,
            keyword=keyword,
            location=location,
            num_pages=num_pages,
            status="pending",
        )
        db.add(scraping_job)
        await db.flush()
        await db.refresh(scraping_job)
        return scraping_job
    
    @staticmethod
    async def get_scraping_job(db: AsyncSession, job_id: uuid.UUID) -> Optional[ScrapingJob]:
        """Get a scraping job by ID."""
        result = await db.execute(select(ScrapingJob).where(ScrapingJob.id == job_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_scraping_job_status(
        db: AsyncSession,
        job_id: uuid.UUID,
        status: str,
        progress: Optional[int] = None,
        jobs_found: Optional[int] = None,
        jobs_saved: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ScrapingJob]:
        """Update scraping job status."""
        scraping_job = await ScrapingJobCRUD.get_scraping_job(db, job_id)
        if not scraping_job:
            return None
        
        scraping_job.status = status
        if progress is not None:
            scraping_job.progress = progress
        if jobs_found is not None:
            scraping_job.jobs_found = jobs_found
        if jobs_saved is not None:
            scraping_job.jobs_saved = jobs_saved
        if error_message is not None:
            scraping_job.error_message = error_message
        
        if status == "running" and not scraping_job.started_at:
            scraping_job.started_at = datetime.utcnow()
        elif status in ["completed", "failed"]:
            scraping_job.completed_at = datetime.utcnow()
        
        await db.flush()
        await db.refresh(scraping_job)
        return scraping_job

"""
SQLAlchemy ORM Models for AutoApply AI.
Defines all database tables and relationships.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Enum as SQLEnum,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func


Base = declarative_base()


# ============================================================================
# Enums
# ============================================================================

class JobSource(str, enum.Enum):
    """Job listing source platforms."""
    NAUKRI = "naukri"
    LINKEDIN = "linkedin"
    INSTAHIRE = "instahire"
    MANUAL = "manual"


class JobStatus(str, enum.Enum):
    """Job review status."""
    NEW = "new"
    REVIEWED = "reviewed"
    SHORTLISTED = "shortlisted"
    IGNORED = "ignored"


class ApplicationStatus(str, enum.Enum):
    """Application tracking status."""
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER_RECEIVED = "offer_received"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_REJECTED = "offer_rejected"
    WITHDRAWN = "withdrawn"


class DocumentType(str, enum.Enum):
    """Document type classification."""
    RESUME = "resume"
    COVER_LETTER = "cover_letter"
    OTHER = "other"


class OperationType(str, enum.Enum):
    """AI operation types for cost tracking."""
    JD_ANALYSIS = "jd_analysis"
    RESUME_TAILOR = "resume_tailor"
    COVER_LETTER = "cover_letter"
    MATCH_SCORING = "match_scoring"
    SCRAPING = "scraping"


# ============================================================================
# Models
# ============================================================================

class Job(Base):
    """Job listing model."""
    __tablename__ = "jobs"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core Fields
    job_title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True)
    
    # Salary Information
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), default="INR")
    
    # Job Details
    experience_required = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    job_url = Column(String(1024), unique=True, nullable=False)
    
    # Source & Metadata
    source = Column(SQLEnum(JobSource), default=JobSource.NAUKRI, index=True)
    scraped_date = Column(DateTime(timezone=True), default=func.now())
    posted_date = Column(DateTime(timezone=True), nullable=True)
    
    # AI Analysis
    match_score = Column(Integer, nullable=True)  # 0-100
    jd_analysis = Column(JSON, nullable=True)  # Cached JD analysis
    required_skills = Column(JSON, nullable=True)  # List of skills
    
    # Status
    status = Column(SQLEnum(JobStatus), default=JobStatus.NEW, index=True)
    is_easy_apply = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_job_title_company", "job_title", "company"),
        Index("idx_job_status_score", "status", "match_score"),
        Index("idx_job_source_date", "source", "scraped_date"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "job_title": self.job_title,
            "company": self.company,
            "location": self.location,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "experience_required": self.experience_required,
            "description": self.description,
            "job_url": self.job_url,
            "source": self.source.value if self.source else None,
            "scraped_date": self.scraped_date.isoformat() if self.scraped_date else None,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "match_score": self.match_score,
            "jd_analysis": self.jd_analysis,
            "required_skills": self.required_skills,
            "status": self.status.value if self.status else None,
            "is_easy_apply": self.is_easy_apply,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Application(Base):
    """Job application tracking model."""
    __tablename__ = "applications"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Relationships
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    
    # Status
    status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.PENDING, index=True)
    
    # Application Details
    applied_date = Column(DateTime(timezone=True), nullable=True)
    resume_version = Column(String(512), nullable=True)  # Path to tailored resume
    cover_letter_path = Column(String(512), nullable=True)
    
    # Notes & Tracking
    notes = Column(Text, nullable=True)
    follow_up_date = Column(DateTime(timezone=True), nullable=True)
    
    # Interview Details
    interview_date = Column(DateTime(timezone=True), nullable=True)
    interview_notes = Column(Text, nullable=True)
    interview_type = Column(String(100), nullable=True)  # phone, video, onsite
    
    # Offer Details
    offer_amount = Column(Integer, nullable=True)
    offer_currency = Column(String(10), default="INR")
    offer_details = Column(JSON, nullable=True)
    
    # Timeline (array of status changes with timestamps)
    timeline = Column(JSON, default=list)
    
    # Match Score at application time
    match_score_at_apply = Column(Integer, nullable=True)
    tailoring_level = Column(String(20), nullable=True)  # conservative, moderate, aggressive
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="applications")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_application_status", "status"),
        Index("idx_application_job", "job_id"),
        Index("idx_application_dates", "applied_date", "follow_up_date"),
    )
    
    def add_timeline_event(self, status: str, notes: Optional[str] = None) -> None:
        """Add event to timeline."""
        if self.timeline is None:
            self.timeline = []
        self.timeline.append({
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "notes": notes,
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "job_id": str(self.job_id),
            "status": self.status.value if self.status else None,
            "applied_date": self.applied_date.isoformat() if self.applied_date else None,
            "resume_version": self.resume_version,
            "cover_letter_path": self.cover_letter_path,
            "notes": self.notes,
            "follow_up_date": self.follow_up_date.isoformat() if self.follow_up_date else None,
            "interview_date": self.interview_date.isoformat() if self.interview_date else None,
            "interview_notes": self.interview_notes,
            "interview_type": self.interview_type,
            "offer_amount": self.offer_amount,
            "offer_currency": self.offer_currency,
            "offer_details": self.offer_details,
            "timeline": self.timeline,
            "match_score_at_apply": self.match_score_at_apply,
            "tailoring_level": self.tailoring_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Document(Base):
    """Document storage model for resumes and cover letters."""
    __tablename__ = "documents"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Relationships
    application_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("applications.id", ondelete="CASCADE"), 
        nullable=True
    )
    
    # Document Details
    document_type = Column(SQLEnum(DocumentType), default=DocumentType.OTHER)
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)  # bytes
    mime_type = Column(String(100), nullable=True)
    
    # Metadata
    is_base_resume = Column(Boolean, default=False)  # Original resume template
    version = Column(Integer, default=1)
    description = Column(Text, nullable=True)
    
    # Timestamps
    uploaded_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "application_id": str(self.application_id) if self.application_id else None,
            "document_type": self.document_type.value if self.document_type else None,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "is_base_resume": self.is_base_resume,
            "version": self.version,
            "description": self.description,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class CostTracking(Base):
    """LLM API cost tracking model."""
    __tablename__ = "cost_tracking"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Operation Details
    operation_type = Column(SQLEnum(OperationType), nullable=False, index=True)
    model_used = Column(String(100), nullable=False)
    
    # Token Usage
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    
    # Cost
    cost_usd = Column(Float, default=0.0)
    
    # Context
    job_id = Column(UUID(as_uuid=True), nullable=True)  # Optional reference to job
    description = Column(Text, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), default=func.now(), index=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_cost_operation_date", "operation_type", "timestamp"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "operation_type": self.operation_type.value if self.operation_type else None,
            "model_used": self.model_used,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "job_id": str(self.job_id) if self.job_id else None,
            "description": self.description,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class ScrapingJob(Base):
    """Background scraping job tracking."""
    __tablename__ = "scraping_jobs"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Job Configuration
    platform = Column(SQLEnum(JobSource), nullable=False)
    keyword = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    num_pages = Column(Integer, default=5)
    
    # Status
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # Percentage
    
    # Results
    jobs_found = Column(Integer, default=0)
    jobs_saved = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "platform": self.platform.value if self.platform else None,
            "keyword": self.keyword,
            "location": self.location,
            "num_pages": self.num_pages,
            "status": self.status,
            "progress": self.progress,
            "jobs_found": self.jobs_found,
            "jobs_saved": self.jobs_saved,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

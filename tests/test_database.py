"""
Tests for database CRUD operations.
"""
import pytest
import uuid
from datetime import datetime

from database.models import Job, JobSource, JobStatus
from database.crud import JobCRUD


@pytest.mark.asyncio
async def test_add_job(db_session, sample_job_data):
    """Test adding a new job."""
    job = await JobCRUD.add_job(db_session, sample_job_data)
    
    assert job.id is not None
    assert job.job_title == sample_job_data["job_title"]
    assert job.company == sample_job_data["company"]
    assert job.status == JobStatus.NEW


@pytest.mark.asyncio
async def test_get_job(db_session, sample_job_data):
    """Test getting a job by ID."""
    job = await JobCRUD.add_job(db_session, sample_job_data)
    
    retrieved = await JobCRUD.get_job(db_session, job.id)
    
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.job_title == job.job_title


@pytest.mark.asyncio
async def test_get_job_by_url(db_session, sample_job_data):
    """Test getting a job by URL."""
    job = await JobCRUD.add_job(db_session, sample_job_data)
    
    retrieved = await JobCRUD.get_job_by_url(db_session, sample_job_data["job_url"])
    
    assert retrieved is not None
    assert retrieved.id == job.id


@pytest.mark.asyncio
async def test_get_jobs_with_filters(db_session, sample_job_data):
    """Test getting jobs with filters."""
    # Add multiple jobs
    job1 = await JobCRUD.add_job(db_session, sample_job_data)
    
    sample_job_data2 = sample_job_data.copy()
    sample_job_data2["job_url"] = "https://example.com/job/99999"
    sample_job_data2["location"] = "Mumbai"
    job2 = await JobCRUD.add_job(db_session, sample_job_data2)
    
    # Filter by location
    jobs, total = await JobCRUD.get_jobs(db_session, location="Bangalore")
    
    assert total >= 1
    assert any(j.location == "Bangalore" for j in jobs)


@pytest.mark.asyncio
async def test_update_job_status(db_session, sample_job_data):
    """Test updating job status."""
    job = await JobCRUD.add_job(db_session, sample_job_data)
    
    updated = await JobCRUD.update_job_status(db_session, job.id, JobStatus.SHORTLISTED)
    
    assert updated is not None
    assert updated.status == JobStatus.SHORTLISTED


@pytest.mark.asyncio
async def test_delete_job(db_session, sample_job_data):
    """Test deleting a job."""
    job = await JobCRUD.add_job(db_session, sample_job_data)
    
    deleted = await JobCRUD.delete_job(db_session, job.id)
    assert deleted is True
    
    # Verify deletion
    retrieved = await JobCRUD.get_job(db_session, job.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_get_jobs_stats(db_session, sample_job_data):
    """Test getting job statistics."""
    # Add some jobs
    await JobCRUD.add_job(db_session, sample_job_data)
    
    sample_job_data2 = sample_job_data.copy()
    sample_job_data2["job_url"] = "https://example.com/job/88888"
    await JobCRUD.add_job(db_session, sample_job_data2)
    
    stats = await JobCRUD.get_jobs_stats(db_session)
    
    assert "total" in stats
    assert stats["total"] >= 2
    assert "new" in stats

"""
Initialize database and create sample jobs.
Run this script to set up the database with sample data.
"""
import asyncio
import uuid
from datetime import datetime, timedelta
import random

# Import using the correct path
import sys
sys.path.insert(0, '/Users/bandaruvinay/Desktop/Job Automation/autoapply-ai')

from database.crud import init_db, get_db, JobCRUD, get_async_db
from database.models import JobStatus, JobSource


# Sample job data
SAMPLE_JOBS = [
    {
        "job_title": "Senior AI/ML Engineer",
        "company": "Google",
        "location": "Bangalore, India",
        "salary_min": 3500000,
        "salary_max": 5500000,
        "description": "We are looking for a Senior AI/ML Engineer to join our team. You will work on cutting-edge machine learning projects.",
        "job_url": "https://careers.google.com/jobs/12345",
        "source": JobSource.LINKEDIN,
        "status": JobStatus.NEW,
        "match_score": 92,
        "required_skills": ["Python", "TensorFlow", "PyTorch", "Kubernetes", "GCP"],
        "is_easy_apply": True,
        "posted_date": datetime.now() - timedelta(days=2),
    },
    {
        "job_title": "Machine Learning Engineer",
        "company": "Microsoft",
        "location": "Hyderabad, India",
        "salary_min": 3000000,
        "salary_max": 4500000,
        "description": "Join Microsoft's AI team to build intelligent products used by millions.",
        "job_url": "https://careers.microsoft.com/jobs/67890",
        "source": JobSource.NAUKRI,
        "status": JobStatus.NEW,
        "match_score": 88,
        "required_skills": ["Python", "Azure ML", "Deep Learning", "NLP", "SQL"],
        "is_easy_apply": False,
        "posted_date": datetime.now() - timedelta(days=1),
    },
    {
        "job_title": "Data Scientist",
        "company": "Amazon",
        "location": "Bangalore, India",
        "salary_min": 2800000,
        "salary_max": 4200000,
        "description": "Amazon is seeking a Data Scientist to drive analytics and ML initiatives.",
        "job_url": "https://amazon.jobs/jobs/98765",
        "source": JobSource.LINKEDIN,
        "status": JobStatus.NEW,
        "match_score": 85,
        "required_skills": ["Python", "SQL", "Machine Learning", "Statistics", "AWS"],
        "is_easy_apply": True,
        "posted_date": datetime.now() - timedelta(days=3),
    },
    {
        "job_title": "AI Research Engineer",
        "company": "Flipkart",
        "location": "Bangalore, India",
        "salary_min": 2500000,
        "salary_max": 4000000,
        "description": "Work on AI/ML solutions for India's largest e-commerce platform.",
        "job_url": "https://flipkart.com/careers/12345",
        "source": JobSource.NAUKRI,
        "status": JobStatus.SHORTLISTED,
        "match_score": 78,
        "required_skills": ["Python", "Deep Learning", "Computer Vision", "Spark"],
        "is_easy_apply": True,
        "posted_date": datetime.now() - timedelta(days=5),
    },
    {
        "job_title": "Full Stack Developer",
        "company": "Swiggy",
        "location": "Bangalore, India",
        "salary_min": 2000000,
        "salary_max": 3500000,
        "description": "Build features for Swiggy's food delivery platform.",
        "job_url": "https://swiggy.com/careers/54321",
        "source": JobSource.INSTAHIRE,
        "status": JobStatus.NEW,
        "match_score": 72,
        "required_skills": ["React", "Node.js", "Python", "MongoDB", "AWS"],
        "is_easy_apply": True,
        "posted_date": datetime.now() - timedelta(days=1),
    },
    {
        "job_title": "Backend Engineer - Python",
        "company": "Razorpay",
        "location": "Bangalore, India",
        "salary_min": 2200000,
        "salary_max": 3800000,
        "description": "Build scalable payment infrastructure using Python.",
        "job_url": "https://razorpay.com/careers/backend",
        "source": JobSource.LINKEDIN,
        "status": JobStatus.NEW,
        "match_score": 82,
        "required_skills": ["Python", "Django", "PostgreSQL", "Redis", "Docker"],
        "is_easy_apply": False,
        "posted_date": datetime.now() - timedelta(days=4),
    },
]


async def init_and_populate():
    """Initialize database and add sample jobs."""
    print("Initializing database...")
    
    # Initialize tables
    init_db()
    print("✅ Database tables created")
    
    # Add sample jobs
    async with get_async_db() as db:
        for job_data in SAMPLE_JOBS:
            try:
                # Check if job already exists
                existing = await JobCRUD.get_job_by_url(db, job_data["job_url"])
                if not existing:
                    await JobCRUD.add_job(db, job_data)
                    print(f"✅ Added: {job_data['job_title']} at {job_data['company']}")
                else:
                    print(f"⏭️ Skipped (exists): {job_data['job_title']} at {job_data['company']}")
            except Exception as e:
                print(f"❌ Error adding {job_data['job_title']}: {e}")
    
    print("\n🎉 Database initialization complete!")
    print(f"Added {len(SAMPLE_JOBS)} sample jobs")


if __name__ == "__main__":
    asyncio.run(init_and_populate())

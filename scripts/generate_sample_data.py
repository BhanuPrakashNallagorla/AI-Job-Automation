"""
Sample Data Generator.
Creates 20 sample jobs for testing.
"""
import asyncio
import random
from datetime import datetime, timedelta
from uuid import uuid4

from database.models import JobSource, JobStatus
from database.crud import init_async_db, JobCRUD, get_async_db


# Sample data
COMPANIES = [
    "Google", "Microsoft", "Amazon", "Meta", "Apple", "Netflix", "Uber",
    "Flipkart", "Swiggy", "Zomato", "Paytm", "PhonePe", "Razorpay",
    "Ola", "CRED", "Zerodha", "Freshworks", "Zoho", "Infosys", "TCS"
]

LOCATIONS = [
    "Bangalore", "Mumbai", "Delhi NCR", "Hyderabad", "Pune",
    "Chennai", "Gurgaon", "Noida", "Remote"
]

JOB_TITLES = [
    "Senior Python Developer",
    "Full Stack Engineer",
    "ML Engineer",
    "Data Scientist",
    "Backend Developer",
    "DevOps Engineer",
    "Software Engineer II",
    "Lead Engineer",
    "SDE III",
    "Platform Engineer",
    "AI/ML Engineer",
    "Senior Software Engineer",
    "Staff Engineer",
    "Cloud Architect",
    "Data Engineer",
]

SKILLS = [
    ["Python", "Django", "PostgreSQL", "Redis", "Docker"],
    ["JavaScript", "React", "Node.js", "MongoDB", "AWS"],
    ["Python", "TensorFlow", "PyTorch", "MLflow", "Kubernetes"],
    ["Python", "SQL", "Spark", "Airflow", "Tableau"],
    ["Go", "gRPC", "Kafka", "PostgreSQL", "Kubernetes"],
    ["AWS", "Terraform", "Docker", "CI/CD", "Prometheus"],
    ["Java", "Spring Boot", "MySQL", "Redis", "Kafka"],
    ["Python", "FastAPI", "GraphQL", "PostgreSQL", "Docker"],
]

DESCRIPTIONS = [
    """We are looking for a passionate engineer to join our team and help build 
    scalable systems. You will work on challenging problems and collaborate with 
    world-class engineers. Requirements: 5+ years experience, strong fundamentals, 
    excellent communication skills.""",
    
    """Join our rapidly growing team to build the next generation of our platform. 
    You'll work on high-impact projects that serve millions of users. We value 
    ownership, innovation, and continuous learning.""",
    
    """We're seeking a talented engineer to help us revolutionize the industry. 
    You'll design and implement robust solutions, mentor junior developers, and 
    drive technical excellence. Competitive compensation and equity.""",
    
    """Exciting opportunity to work on cutting-edge technology in a fast-paced 
    environment. You'll own critical systems and make architectural decisions. 
    We offer flexible work arrangements and great benefits.""",
]


def generate_salary():
    """Generate random salary range."""
    min_salary = random.choice([800000, 1000000, 1500000, 2000000, 2500000, 3000000])
    max_salary = min_salary + random.choice([300000, 500000, 800000, 1000000])
    return min_salary, max_salary


def generate_experience():
    """Generate experience requirement."""
    options = ["0-2 years", "2-4 years", "3-5 years", "5-8 years", "8+ years", "10+ years"]
    return random.choice(options)


async def generate_sample_jobs(count: int = 20):
    """Generate sample job data."""
    print(f"Generating {count} sample jobs...")
    
    await init_async_db()
    
    jobs_created = 0
    
    async with get_async_db() as db:
        for i in range(count):
            salary_min, salary_max = generate_salary()
            
            job_data = {
                "job_title": random.choice(JOB_TITLES),
                "company": random.choice(COMPANIES),
                "location": random.choice(LOCATIONS),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_currency": "INR",
                "experience_required": generate_experience(),
                "description": random.choice(DESCRIPTIONS),
                "job_url": f"https://example.com/job/{uuid4().hex[:12]}",
                "source": random.choice([JobSource.NAUKRI, JobSource.LINKEDIN, JobSource.INSTAHIRE]),
                "status": random.choice([JobStatus.NEW, JobStatus.NEW, JobStatus.NEW, JobStatus.REVIEWED]),
                "required_skills": random.choice(SKILLS),
                "is_easy_apply": random.choice([True, False]),
                "posted_date": datetime.now() - timedelta(days=random.randint(1, 14)),
                "scraped_date": datetime.now() - timedelta(hours=random.randint(1, 48)),
                "match_score": random.randint(40, 95) if random.random() > 0.5 else None,
            }
            
            try:
                await JobCRUD.add_job(db, job_data)
                jobs_created += 1
                print(f"  Created: {job_data['job_title']} at {job_data['company']}")
            except Exception as e:
                print(f"  Failed: {e}")
    
    print(f"\n✓ Created {jobs_created} sample jobs")
    return jobs_created


if __name__ == "__main__":
    asyncio.run(generate_sample_jobs(20))

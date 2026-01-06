"""
Test configuration and fixtures.
"""
import pytest
import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base


# Use SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_DATABASE_URL_SYNC = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine():
    """Create async test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for each test."""
    async_session_maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sync_engine():
    """Create sync test database engine."""
    engine = create_engine(TEST_DATABASE_URL_SYNC, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def sync_session(sync_engine):
    """Create sync database session."""
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# Mock data fixtures
@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "job_title": "Senior Python Developer",
        "company": "TechCorp",
        "location": "Bangalore",
        "salary_min": 2000000,
        "salary_max": 3000000,
        "experience_required": "5-8 years",
        "description": "Looking for a Python developer with Django experience",
        "job_url": "https://example.com/job/12345",
    }


@pytest.fixture
def sample_jd():
    """Sample job description for testing."""
    return """
    We are looking for a Senior Python Developer to join our team.
    
    Requirements:
    - 5+ years of Python experience
    - Strong knowledge of Django and FastAPI
    - Experience with PostgreSQL and Redis
    - Familiarity with Docker and Kubernetes
    - AWS experience preferred
    
    Responsibilities:
    - Design and implement scalable APIs
    - Write clean, maintainable code
    - Mentor junior developers
    - Participate in code reviews
    
    Nice to have:
    - Machine learning experience
    - Open source contributions
    
    We offer competitive salary (25-35 LPA), equity, and flexible work.
    """


@pytest.fixture
def sample_resume():
    """Sample resume text for testing."""
    return """
    John Doe
    Senior Software Engineer
    john.doe@email.com | +91-9876543210 | Bangalore
    
    Summary:
    6 years of experience in building scalable web applications using Python.
    
    Skills:
    - Languages: Python, JavaScript, SQL
    - Frameworks: Django, Flask, React
    - Databases: PostgreSQL, Redis, MongoDB
    - Tools: Docker, Git, CI/CD
    - Cloud: AWS (EC2, S3, Lambda)
    
    Experience:
    
    Senior Software Engineer | TechStartup | 2021-Present
    - Built high-performance REST APIs serving 1M+ requests/day
    - Reduced API latency by 40% through caching optimization
    - Led migration from monolith to microservices
    
    Software Engineer | BigCorp | 2018-2021
    - Developed Django-based web applications
    - Implemented CI/CD pipelines
    
    Education:
    B.Tech Computer Science | IIT Delhi | 2018
    """

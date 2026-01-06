"""
API routes module initialization.
"""
from api.routes.jobs import router as jobs_router
from api.routes.applications import router as applications_router
from api.routes.scraper import router as scraper_router
from api.routes.ai import router as ai_router

__all__ = [
    "jobs_router",
    "applications_router", 
    "scraper_router",
    "ai_router",
]

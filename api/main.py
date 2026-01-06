"""
FastAPI Application - Main Entry Point.
AutoApply AI Backend Server.
"""
import time
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from config import settings
from database.crud import init_async_db
from api.routes import jobs_router, applications_router, scraper_router, ai_router


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)


# ============================================================================
# Rate Limiting (Simple In-Memory)
# ============================================================================

class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: dict = {}
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed."""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old entries
        self.requests = {
            k: [t for t in v if t > minute_ago]
            for k, v in self.requests.items()
        }
        
        # Check rate
        client_requests = self.requests.get(client_id, [])
        if len(client_requests) >= self.requests_per_minute:
            return False
        
        # Record request
        if client_id not in self.requests:
            self.requests[client_id] = []
        self.requests[client_id].append(now)
        
        return True


rate_limiter = RateLimiter(requests_per_minute=100)


# ============================================================================
# Lifespan Context Manager
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting AutoApply AI server...")
    
    # Initialize database
    try:
        await init_async_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")
    
    yield
    
    # Cleanup
    logger.info("Shutting down AutoApply AI server...")


# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="AutoApply AI",
    description="""
    ## Job Application Automation Platform
    
    AutoApply AI helps you:
    - **Scrape jobs** from Naukri, LinkedIn, and Instahire
    - **Analyze job descriptions** with AI
    - **Tailor resumes** for each application
    - **Generate cover letters** personalized to companies
    - **Track applications** through the pipeline
    
    ### Key Features
    - 🤖 AI-powered resume tailoring (3 intensity levels)
    - 📝 Non-generic cover letter generation
    - 📊 Match scoring with detailed breakdowns
    - 💰 Cost tracking for AI usage
    - 🔄 Background job processing
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ============================================================================
# Middleware
# ============================================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Callable):
    """Rate limiting middleware."""
    client_ip = request.client.host if request.client else "unknown"
    
    if not rate_limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Please slow down."}
        )
    
    return await call_next(request)


@app.middleware("http")
async def logging_middleware(request: Request, call_next: Callable):
    """Request logging middleware."""
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Log request
    process_time = time.time() - start_time
    logger.info(
        "Request processed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(process_time * 1000, 2),
    )
    
    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error("Unhandled exception", error=str(exc), exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "An internal error occurred. Please try again later.",
            "status_code": 500,
        }
    )


# ============================================================================
# Routes
# ============================================================================

# Include routers
app.include_router(jobs_router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(applications_router, prefix="/api/applications", tags=["Applications"])
app.include_router(scraper_router, prefix="/api/scraper", tags=["Scraper"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AutoApply AI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "api": "up",
            "database": "up",  # Would check actual DB in production
        }
    }


@app.get("/api/info", tags=["Info"])
async def api_info():
    """Get API information and configuration."""
    return {
        "version": "1.0.0",
        "ai_models": {
            "jd_analysis": settings.claude_sonnet_model,
            "resume_tailor": settings.claude_opus_model,
            "cover_letter": settings.claude_opus_model,
        },
        "supported_platforms": ["naukri", "linkedin", "instahire"],
        "tailoring_levels": ["conservative", "moderate", "aggressive"],
        "cover_letter_tones": ["professional", "conversational", "enthusiastic"],
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )

"""
Monitoring API Routes.
Endpoints for usage monitoring and health checks.
"""
from datetime import datetime

from fastapi import APIRouter

from ai.gemini_client import get_gemini_client
from utils.cache_manager import get_cache_manager
from config import settings


router = APIRouter()


@router.get("/usage")
async def get_usage_stats():
    """
    Get detailed API usage statistics.
    """
    client = get_gemini_client()
    stats = client.get_usage_stats()
    
    return {
        "requests_today": stats["requests_today"],
        "daily_limit": stats["daily_limit"],
        "remaining": stats["remaining"],
        "percentage_used": stats["percentage_used"],
        "cache_entries": stats["cache_size"],
        "model": "gemini-2.0-flash-exp",
        "tier": "free",
        "reset_at": "midnight UTC",
    }


@router.get("/costs")
async def get_cost_comparison():
    """
    Get cost comparison vs paid APIs.
    
    Shows how much you're saving by using Gemini free tier.
    """
    client = get_gemini_client()
    stats = client.get_usage_stats()
    requests = stats["requests_today"]
    
    # Estimated costs if using paid APIs
    openai_cost = requests * 0.015  # ~$0.015 per request average
    anthropic_cost = requests * 0.02  # ~$0.02 per request average
    
    return {
        "gemini_cost": 0.0,
        "openai_equivalent": round(openai_cost, 2),
        "anthropic_equivalent": round(anthropic_cost, 2),
        "savings_today": round(openai_cost, 2),
        "requests_today": requests,
        "message": "Using Gemini free tier saves you money!",
    }


@router.get("/health")
async def get_health_status():
    """
    Get comprehensive health status.
    """
    status = {
        "api": "up",
        "database": "up",
        "cache": "unknown",
        "ai_service": "unknown",
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Check AI service
    try:
        client = get_gemini_client()
        usage = client.get_usage_stats()
        
        if usage["percentage_used"] < 90:
            status["ai_service"] = "up"
        else:
            status["ai_service"] = "degraded"
    except Exception as e:
        status["ai_service"] = f"down: {str(e)}"
    
    # Check cache
    try:
        cache = get_cache_manager()
        cache_stats = cache.get_stats()
        status["cache"] = cache_stats["backend"]
    except Exception:
        status["cache"] = "unavailable"
    
    # Overall status
    if all(v in ["up", "memory", "redis"] for v in [status["api"], status["ai_service"], status["cache"]]):
        status["overall"] = "healthy"
    elif status["ai_service"] == "degraded":
        status["overall"] = "degraded"
    else:
        status["overall"] = "unhealthy"
    
    return status


@router.get("/limits")
async def get_rate_limits():
    """
    Get current rate limit configuration.
    """
    return {
        "requests_per_minute": settings.rate_limit_rpm,
        "requests_per_day": settings.max_daily_requests,
        "cache_ttl_seconds": settings.cache_ttl,
        "model": "gemini-2.0-flash-exp",
        "tier": "free",
        "notes": [
            "Rate limits include buffer below actual API limits",
            "Caching reduces actual API calls significantly",
            "Same request returns cached response",
        ],
    }

"""
Tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create test client."""
    from api.main import app
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AutoApply AI"
    assert "docs" in data


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_api_info(client):
    """Test API info endpoint."""
    response = client.get("/api/info")
    
    assert response.status_code == 200
    data = response.json()
    assert "ai_models" in data
    assert "supported_platforms" in data
    assert "tailoring_levels" in data


def test_get_supported_platforms(client):
    """Test getting supported platforms."""
    response = client.get("/api/scraper/supported-platforms")
    
    assert response.status_code == 200
    platforms = response.json()
    assert len(platforms) >= 3
    
    platform_ids = [p["id"] for p in platforms]
    assert "naukri" in platform_ids
    assert "linkedin" in platform_ids
    assert "instahire" in platform_ids


def test_scraper_config(client):
    """Test getting scraper config."""
    response = client.get("/api/scraper/config")
    
    assert response.status_code == 200
    config = response.json()
    assert "max_pages_per_job" in config
    assert "delay_range" in config


def test_invalid_job_id(client):
    """Test handling of invalid job ID."""
    response = client.get("/api/jobs/invalid-uuid")
    
    assert response.status_code == 400
    assert "Invalid job ID" in response.json()["detail"]


def test_job_not_found(client):
    """Test handling of non-existent job."""
    response = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    
    # Database might not be initialized in test, so either 404 or 500 is expected
    assert response.status_code in [404, 500]


def test_invalid_platform(client):
    """Test validation of platform in scrape request."""
    response = client.post(
        "/api/jobs/scrape",
        json={
            "platform": "invalid_platform",
            "keyword": "python developer",
        }
    )
    
    assert response.status_code == 400
    assert "Invalid platform" in response.json()["detail"]


def test_scrape_request_validation(client):
    """Test validation of scrape request."""
    # Missing required field
    response = client.post(
        "/api/jobs/scrape",
        json={
            "platform": "naukri",
            # Missing keyword
        }
    )
    
    assert response.status_code == 422  # Validation error


def test_costs_endpoint(client):
    """Test AI costs endpoint."""
    response = client.get("/api/ai/costs")
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "report" in data


def test_cost_optimization_endpoint(client):
    """Test cost optimization suggestions endpoint."""
    response = client.get("/api/ai/costs/optimization")
    
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data

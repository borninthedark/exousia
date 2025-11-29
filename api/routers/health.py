"""
Health Check Router
===================

Endpoints for API health and status monitoring.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..database import get_db
from ..models import HealthResponse
from ..config import settings
from ..services.github_service import GitHubService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.

    Returns the API status, version, and service health.
    """
    # Check database
    db_status = "healthy"
    try:
        await db.execute("SELECT 1")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Check GitHub API
    github_status = "healthy"
    if settings.GITHUB_TOKEN:
        try:
            github_service = GitHubService(settings.GITHUB_TOKEN, settings.GITHUB_REPO)
            # Simple check - try to get repo info
            await github_service.get_repo()
        except Exception as e:
            github_status = f"unhealthy: {str(e)}"
    else:
        github_status = "not configured"

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        version="0.1.0",
        database=db_status,
        github=github_status,
        timestamp=datetime.utcnow()
    )


@router.get("/ping")
async def ping():
    """Simple ping endpoint for uptime monitoring."""
    return {"ping": "pong", "timestamp": datetime.utcnow()}

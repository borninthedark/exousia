"""
Health Check Router
===================

Endpoints for API health and status monitoring.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Check GitHub API
    github_status = "healthy"
    if settings.GITHUB_TOKEN:
        try:
            github_service = GitHubService(settings.GITHUB_TOKEN, settings.GITHUB_REPO)
            # Simple check - try to get repo info
            await github_service.get_repo()
        except Exception:
            github_status = "unhealthy"
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

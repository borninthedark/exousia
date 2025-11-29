#!/usr/bin/env python3
"""
Exousia API - FastAPI Backend
==============================

REST API for managing YAML configurations, transpiling to Containerfiles,
and integrating with GitHub Actions for automated builds.

Features:
- YAML configuration validation and transpilation
- GitHub Actions integration for build triggering
- Build status tracking
- Configuration versioning and storage
- Real-time preview generation
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from pathlib import Path

from .routers import config, build, health
from .database import init_db, close_db
from .config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Exousia API...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    yield

    # Cleanup
    logger.info("Shutting down Exousia API...")
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="Exousia API",
    description="REST API for declarative bootc image configuration management",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS middleware for web UI integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "detail": exc.detail,
            "status": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status": 500
        }
    )


# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(build.router, prefix="/api/build", tags=["build"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Exousia API",
        "version": "0.1.0",
        "description": "REST API for declarative bootc image configuration",
        "docs": "/api/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

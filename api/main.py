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

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator

from .routers import config, build, health
from .database import init_db, close_db
from .config import settings
from .auth import (
    auth_backend,
    current_active_user,
    fastapi_users,
    UserCreate,
    UserRead,
    UserUpdate,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
instrumentator = Instrumentator()


def _parse_otlp_headers(header_string: str | None) -> dict[str, str]:
    if not header_string:
        return {}
    header_pairs = [pair.strip() for pair in header_string.split(",") if pair.strip()]
    headers: dict[str, str] = {}
    for pair in header_pairs:
        if "=" in pair:
            key, value = pair.split("=", 1)
            headers[key.strip()] = value.strip()
    return headers


def setup_tracing(app: FastAPI) -> None:
    if not settings.ENABLE_TRACING:
        logger.info("Tracing is disabled.")
        return

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    tracer_provider = TracerProvider(resource=resource)

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            headers=_parse_otlp_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(tracer_provider)
    FastAPIInstrumentor.instrument_app(app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Exousia API...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    setup_tracing(app)
    instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

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
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/api/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/users",
    tags=["users"],
)


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

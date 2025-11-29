"""
Middleware Stack
================

Custom middleware for security, observability, and rate limiting.
Inspired by witness repository patterns.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import time
import uuid
import logging

logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Add correlation ID to each request for distributed tracing."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with structured logging."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        logger.info(
            "Request started",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else "unknown"
            }
        )

        response = await call_next(request)

        duration = time.time() - start_time

        logger.info(
            "Request completed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
        )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # CSP for API (strict)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'"
        )

        return response


def configure_middleware(app):
    """Configure all middleware for the FastAPI application."""

    # Order matters! Add from outermost to innermost

    # 1. GZip compression (outermost)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 2. Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Correlation ID for request tracking
    app.add_middleware(CorrelationIDMiddleware)

    # 4. Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # 5. Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    return app

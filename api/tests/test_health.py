"""
Tests for Health Endpoints
===========================
"""

import pytest
from httpx import AsyncClient


@pytest.mark.unit
class TestHealthEndpoints:
    """Test health and status endpoints."""

    async def test_ping(self, client: AsyncClient):
        """Test ping endpoint returns pong."""
        response = await client.get("/api/ping")
        assert response.status_code == 200

        data = response.json()
        assert "ping" in data
        assert data["ping"] == "pong"
        assert "timestamp" in data

    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint returns status."""
        response = await client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data
        assert "github" in data
        assert "timestamp" in data

        assert data["version"] == "0.1.0"
        assert data["database"] == "healthy"

    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns API info."""
        response = await client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Exousia API"
        assert data["version"] == "0.1.0"
        assert "/api/docs" in data["docs"]

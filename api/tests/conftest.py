"""
Pytest Configuration and Fixtures
==================================

Shared fixtures for API testing.
"""

import uuid
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.auth import User, current_active_user
from api.database import Base, get_db
from api.main import app

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database for each test function."""
    # Create async engine for test database
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session maker
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Provide session
    async with async_session() as session:
        yield session

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override."""

    async def override_get_db():
        yield test_db

    async def override_current_active_user():
        return User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password="not-used",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_active_user] = override_current_active_user

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sync_client() -> Generator:
    """Create synchronous test client for simple tests."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_yaml_config() -> str:
    """Sample YAML configuration for testing."""
    return """
name: test-config
description: Test configuration
image-version: 43
base-image: quay.io/fedora/fedora-sway-atomic:43
image-type: fedora-sway-atomic

modules:
  - type: rpm-ostree
    install:
      - kitty
      - neovim
    remove:
      - firefox-langpacks
"""


@pytest.fixture
def invalid_yaml_config() -> str:
    """Invalid YAML configuration for testing."""
    return """
name: test
# Missing required fields
"""


@pytest.fixture
async def sample_config(test_db: AsyncSession, sample_yaml_config: str):
    """Create a sample configuration in the database."""
    from api.database import ConfigModel

    config = ConfigModel(
        name="test-config",
        description="Test configuration",
        yaml_content=sample_yaml_config,
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=True,
    )

    test_db.add(config)
    await test_db.commit()
    await test_db.refresh(config)

    return config


@pytest.fixture
async def sample_build(test_db: AsyncSession, sample_config):
    """Create a sample build in the database."""
    from api.database import BuildModel
    from api.models import BuildStatus

    build = BuildModel(
        config_id=sample_config.id,
        workflow_run_id=12345,
        status=BuildStatus.IN_PROGRESS,
        image_type="fedora-sway-atomic",
        fedora_version="43",
        ref="main",
    )

    test_db.add(build)
    await test_db.commit()
    await test_db.refresh(build)

    return build

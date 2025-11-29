"""
Database Models and Configuration
==================================

SQLAlchemy models for configuration and build tracking.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional

from .config import settings
from .models import BuildStatus, ImageType

Base = declarative_base()


# Database Models
class ConfigModel(Base):
    """Configuration storage model with optimistic locking."""
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    yaml_content = Column(Text, nullable=False)
    image_type = Column(String(50), nullable=False, default="fedora-sway-atomic")
    fedora_version = Column(String(20), nullable=False, default="43")
    enable_plymouth = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)  # Optimistic locking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_config_name_version', 'name', 'version'),
    )


class BuildModel(Base):
    """Build tracking model with optimistic locking."""
    __tablename__ = "builds"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=True, index=True)
    workflow_run_id = Column(Integer, nullable=True, index=True)
    status = Column(SQLEnum(BuildStatus), nullable=False, default=BuildStatus.PENDING)
    image_type = Column(String(50), nullable=False)
    fedora_version = Column(String(20), nullable=False)
    ref = Column(String(100), nullable=False, default="main")
    version = Column(Integer, nullable=False, default=1)  # Optimistic locking
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to events
    events = relationship("BuildEventModel", back_populates="build", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_build_status', 'status'),
        Index('idx_build_config_ref', 'config_id', 'ref', 'status'),
    )


class BuildEventModel(Base):
    """Immutable event log for build state transitions (Event Sourcing)."""
    __tablename__ = "build_events"

    id = Column(Integer, primary_key=True, index=True)
    build_id = Column(Integer, ForeignKey("builds.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # e.g., "status_changed", "workflow_triggered"
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=True)
    metadata = Column(JSON, nullable=True)  # Additional event data
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    build = relationship("BuildModel", back_populates="events")

    __table_args__ = (
        Index('idx_build_event_build_id', 'build_id'),
        Index('idx_build_event_timestamp', 'timestamp'),
        Index('idx_build_event_type', 'event_type'),
    )


# Database engine and session
engine = None
async_session_maker = None


async def init_db():
    """Initialize database engine and create tables."""
    global engine, async_session_maker

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.LOG_LEVEL == "DEBUG",
        future=True
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    global engine
    if engine:
        await engine.dispose()


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

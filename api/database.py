"""Database models and session helpers for the API layer."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .config import settings
from .models import BuildStatus


class Base(DeclarativeBase):
    """Shared declarative base for SQLAlchemy models."""

    pass


# Database Models
class ConfigModel(Base):
    """Configuration storage model with optimistic locking."""

    __tablename__ = "configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    yaml_content: Mapped[str] = mapped_column(Text, nullable=False)
    image_type: Mapped[str] = mapped_column(String(50), nullable=False, default="fedora-sway-atomic")
    fedora_version: Mapped[str] = mapped_column(String(20), nullable=False, default="43")
    enable_plymouth: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # Optimistic locking
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index('idx_config_name_version', 'name', 'version'),
    )


class BuildModel(Base):
    """Build tracking model with optimistic locking."""

    __tablename__ = "builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    config_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("configs.id"), nullable=True, index=True
    )
    workflow_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[BuildStatus] = mapped_column(
        SQLEnum(BuildStatus), nullable=False, default=BuildStatus.PENDING
    )
    image_type: Mapped[str] = mapped_column(String(50), nullable=False)
    fedora_version: Mapped[str] = mapped_column(String(20), nullable=False)
    ref: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # Optimistic locking
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship to events
    events: Mapped[list["BuildEventModel"]] = relationship(
        "BuildEventModel", back_populates="build", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_build_status', 'status'),
        Index('idx_build_config_ref', 'config_id', 'ref', 'status'),
    )


class BuildEventModel(Base):
    """Immutable event log for build state transitions (Event Sourcing)."""

    __tablename__ = "build_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    build_id: Mapped[int] = mapped_column(Integer, ForeignKey("builds.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "status_changed", "workflow_triggered"
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    event_data: Mapped[Optional[dict[str, object]]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    build: Mapped[BuildModel] = relationship("BuildModel", back_populates="events")

    __table_args__ = (
        Index('idx_build_event_build_id', 'build_id'),
        Index('idx_build_event_timestamp', 'timestamp'),
        Index('idx_build_event_type', 'event_type'),
    )


# Database engine and session
engine = None
async_session_maker = None


def get_alembic_config() -> Config:
    """Load Alembic configuration with the runtime database URL."""
    config_path = Path(__file__).parent / "alembic.ini"
    alembic_config = Config(str(config_path))
    alembic_config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    alembic_config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return alembic_config


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

    # Run migrations
    await asyncio.to_thread(command.upgrade, get_alembic_config(), "head")


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



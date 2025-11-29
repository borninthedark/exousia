"""
Database Models and Configuration
==================================

SQLAlchemy models for configuration and build tracking.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.sql import func
from datetime import datetime

from .config import settings
from .models import BuildStatus, ImageType

Base = declarative_base()


# Database Models
class ConfigModel(Base):
    """Configuration storage model."""
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    yaml_content = Column(Text, nullable=False)
    image_type = Column(String(50), nullable=False, default="fedora-sway-atomic")
    fedora_version = Column(String(20), nullable=False, default="43")
    enable_plymouth = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BuildModel(Base):
    """Build tracking model."""
    __tablename__ = "builds"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=True, index=True)
    workflow_run_id = Column(Integer, nullable=True, index=True)
    status = Column(SQLEnum(BuildStatus), nullable=False, default=BuildStatus.PENDING)
    image_type = Column(String(50), nullable=False)
    fedora_version = Column(String(20), nullable=False)
    ref = Column(String(100), nullable=False, default="main")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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

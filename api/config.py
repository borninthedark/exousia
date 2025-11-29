"""
Application Configuration
=========================

Centralized configuration management using Pydantic Settings.
Supports environment variables and .env files.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path
from enum import Enum


class DeploymentMode(str, Enum):
    """Deployment mode for optimizing architecture."""
    LAPTOP = "laptop"  # Single-node, lightweight, file-based
    CLOUD = "cloud"    # Distributed, scalable, cloud-native


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Deployment Mode
    DEPLOYMENT_MODE: DeploymentMode = DeploymentMode.LAPTOP

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True

    # CORS Settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000"
    ]

    # Database Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./exousia.db"

    # Database Connection Pool (mode-aware)
    @property
    def DB_POOL_SIZE(self) -> int:
        return 5 if self.DEPLOYMENT_MODE == DeploymentMode.LAPTOP else 20

    @property
    def DB_MAX_OVERFLOW(self) -> int:
        return 0 if self.DEPLOYMENT_MODE == DeploymentMode.LAPTOP else 40

    # BlazingMQ Settings
    BLAZINGMQ_ENABLED: bool = True
    BLAZINGMQ_BROKER_URI: str = "tcp://localhost:30114"  # Default BlazingMQ broker
    BLAZINGMQ_DOMAIN: str = "exousia"
    BLAZINGMQ_QUEUE_BUILD: str = "build.queue"
    BLAZINGMQ_QUEUE_DLQ: str = "build.dlq"

    # Queue Settings
    QUEUE_MAX_RETRIES: int = 3
    QUEUE_RETRY_DELAY: int = 60  # seconds
    QUEUE_MESSAGE_TTL: int = 86400  # 24 hours

    # Worker Settings
    WORKER_CONCURRENCY: int = 1 if DEPLOYMENT_MODE == DeploymentMode.LAPTOP else 4
    WORKER_POLL_INTERVAL: int = 5  # seconds

    # GitHub Settings
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = "borninthedark/exousia"
    GITHUB_WORKFLOW_FILE: str = "build.yaml"

    # Repository Paths
    REPO_ROOT: Path = Path(__file__).parent.parent
    CONFIG_FILE: Path = REPO_ROOT / "exousia.yml"
    TRANSPILER_SCRIPT: Path = REPO_ROOT / "tools" / "yaml-to-containerfile.py"
    YAML_DEFINITIONS_DIR: Path = REPO_ROOT / "yaml-definitions"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

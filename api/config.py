"""
Application Configuration
=========================

Centralized configuration management using Pydantic Settings.
Supports environment variables and .env files.
"""

from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with environment variable support."""

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

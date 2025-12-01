"""
Pydantic Models
===============

Request and response models for API endpoints.
"""

from pydantic import BaseModel, Field, root_validator, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ImageType(str, Enum):
    """Supported base image types."""
    FEDORA_BOOTC = "fedora-bootc"
    FEDORA_SWAY_ATOMIC = "fedora-sway-atomic"
    BOOTCREW = "bootcrew"


class BuildStatus(str, Enum):
    """Build status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


# Config Models
class ConfigValidateRequest(BaseModel):
    """Request model for config validation."""
    yaml_content: str = Field(..., description="YAML configuration content")


class ConfigValidateResponse(BaseModel):
    """Response model for config validation."""
    valid: bool
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


class ConfigTranspileRequest(BaseModel):
    """Request model for config transpilation."""
    yaml_content: str = Field(..., description="YAML configuration content")
    image_type: ImageType = Field(ImageType.FEDORA_SWAY_ATOMIC, description="Base image type")
    fedora_version: str = Field("43", description="Fedora version")
    enable_plymouth: bool = Field(True, description="Enable Plymouth boot splash")


class ConfigTranspileResponse(BaseModel):
    """Response model for config transpilation."""
    containerfile: str
    image_type: str
    fedora_version: str
    enable_plymouth: bool


class ConfigCreateRequest(BaseModel):
    """Request model for creating a config."""
    name: str = Field(..., min_length=1, max_length=100, description="Configuration name")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    yaml_content: str = Field(..., description="YAML configuration content")
    image_type: ImageType = Field(ImageType.FEDORA_SWAY_ATOMIC)
    fedora_version: str = Field("43")
    enable_plymouth: bool = Field(True)

    @validator('name')
    def validate_name(cls, v):
        """Validate config name format."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Name must contain only alphanumeric characters, hyphens, and underscores')
        return v


class ConfigResponse(BaseModel):
    """Response model for config operations."""
    id: int
    name: str
    description: Optional[str]
    yaml_content: str
    image_type: str
    fedora_version: str
    enable_plymouth: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConfigListResponse(BaseModel):
    """Response model for listing configs."""
    configs: List[ConfigResponse]
    total: int
    page: int
    page_size: int


class YamlDefinitionFile(BaseModel):
    """Model for a YAML definition file."""
    filename: str
    name: str
    description: Optional[str]
    image_type: Optional[str]
    path: str


class YamlDefinitionsListResponse(BaseModel):
    """Response model for listing YAML definition files."""
    definitions: List[YamlDefinitionFile]
    total: int


# Build Models
class BuildTriggerRequest(BaseModel):
    """Request model for triggering a build."""
    config_id: Optional[int] = Field(None, description="Config ID to build (or use yaml_content/definition_filename)")
    yaml_content: Optional[str] = Field(None, description="YAML content to build (ad-hoc)")
    definition_filename: Optional[str] = Field(None, description="YAML definition filename from yaml-definitions/")
    image_type: ImageType = Field(ImageType.FEDORA_SWAY_ATOMIC)
    fedora_version: str = Field("43")
    enable_plymouth: bool = Field(True)
    window_manager: Optional[str] = Field(None, description="Override window manager for Fedora bootc builds")
    desktop_environment: Optional[str] = Field(None, description="Override desktop environment for Fedora bootc builds")
    ref: str = Field("main", description="Git ref to build from")

    @root_validator(skip_on_failure=True)
    def validate_desktop_selection(cls, values):
        """Ensure only one of window_manager or desktop_environment is provided."""
        wm = values.get("window_manager")
        de = values.get("desktop_environment")

        if wm and de:
            raise ValueError("Specify only one of window_manager or desktop_environment")

        return values


class BuildResponse(BaseModel):
    """Response model for build operations."""
    id: int
    config_id: Optional[int]
    workflow_run_id: Optional[int]
    status: BuildStatus
    image_type: str
    fedora_version: str
    ref: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class BuildStatusResponse(BaseModel):
    """Response model for build status."""
    build: BuildResponse
    workflow_status: Optional[str]
    workflow_url: Optional[str]
    conclusion: Optional[str]
    logs_url: Optional[str]


class BuildListResponse(BaseModel):
    """Response model for listing builds."""
    builds: List[BuildResponse]
    total: int
    page: int
    page_size: int


# GitHub Models
class WorkflowDispatchRequest(BaseModel):
    """Request model for GitHub workflow dispatch."""
    ref: str = "main"
    inputs: Dict[str, Any] = Field(default_factory=dict)


# Health Models
class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    database: str
    github: str
    timestamp: datetime

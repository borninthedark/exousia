"""
Constants and enums shared across tools.
"""
from enum import Enum


class ImageType(str, Enum):
    """Supported base image types."""
    FEDORA_BOOTC = "fedora-bootc"
    FEDORA_SWAY_ATOMIC = "fedora-sway-atomic"


class BuildStatus(str, Enum):
    """Build status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"

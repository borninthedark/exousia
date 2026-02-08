"""
Constants and enums shared across tools.
"""

from enum import StrEnum


class ImageType(StrEnum):
    """Supported base image types."""

    FEDORA_BOOTC = "fedora-bootc"
    FEDORA_SWAY_ATOMIC = "fedora-sway-atomic"


class BuildStatus(StrEnum):
    """Build status enumeration."""

    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"

"""
Configuration Router
====================

Endpoints for YAML configuration management and transpilation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from ..database import get_db, ConfigModel
from ..models import (
    ConfigValidateRequest, ConfigValidateResponse,
    ConfigTranspileRequest, ConfigTranspileResponse,
    ConfigCreateRequest, ConfigResponse, ConfigListResponse
)
from ..services.transpiler_service import TranspilerService

router = APIRouter()


@router.post("/validate", response_model=ConfigValidateResponse)
async def validate_config(request: ConfigValidateRequest):
    """
    Validate YAML configuration.

    Checks YAML syntax and BlueBuild schema compliance.
    """
    transpiler = TranspilerService()
    result = await transpiler.validate(request.yaml_content)

    return ConfigValidateResponse(
        valid=result["valid"],
        errors=result.get("errors"),
        warnings=result.get("warnings")
    )


@router.post("/transpile", response_model=ConfigTranspileResponse)
async def transpile_config(request: ConfigTranspileRequest):
    """
    Transpile YAML configuration to Containerfile.

    Generates a Containerfile from the provided YAML configuration.
    """
    transpiler = TranspilerService()

    try:
        containerfile = await transpiler.transpile(
            yaml_content=request.yaml_content,
            image_type=request.image_type.value,
            fedora_version=request.fedora_version,
            enable_plymouth=request.enable_plymouth
        )

        return ConfigTranspileResponse(
            containerfile=containerfile,
            image_type=request.image_type.value,
            fedora_version=request.fedora_version,
            enable_plymouth=request.enable_plymouth
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transpilation failed: {str(e)}")


@router.post("/", response_model=ConfigResponse, status_code=201)
async def create_config(
    request: ConfigCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new configuration.

    Stores a YAML configuration for later use and builds.
    """
    # Check if name already exists
    result = await db.execute(
        select(ConfigModel).where(ConfigModel.name == request.name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail=f"Configuration '{request.name}' already exists")

    # Validate YAML before saving
    transpiler = TranspilerService()
    validation = await transpiler.validate(request.yaml_content)

    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML configuration: {', '.join(validation.get('errors', []))}"
        )

    # Create config
    config = ConfigModel(
        name=request.name,
        description=request.description,
        yaml_content=request.yaml_content,
        image_type=request.image_type.value,
        fedora_version=request.fedora_version,
        enable_plymouth=request.enable_plymouth
    )

    db.add(config)
    await db.commit()
    await db.refresh(config)

    return config


@router.get("/", response_model=ConfigListResponse)
async def list_configs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    List all configurations with pagination.
    """
    # Get total count
    count_result = await db.execute(select(func.count(ConfigModel.id)))
    total = count_result.scalar()

    # Get paginated configs
    offset = (page - 1) * page_size
    result = await db.execute(
        select(ConfigModel)
        .order_by(ConfigModel.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    configs = result.scalars().all()

    return ConfigListResponse(
        configs=configs,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{config_id}", response_model=ConfigResponse)
async def get_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get a specific configuration by ID.
    """
    result = await db.execute(
        select(ConfigModel).where(ConfigModel.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration {config_id} not found")

    return config


@router.put("/{config_id}", response_model=ConfigResponse)
async def update_config(
    config_id: int,
    request: ConfigCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing configuration.
    """
    result = await db.execute(
        select(ConfigModel).where(ConfigModel.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration {config_id} not found")

    # Validate YAML before updating
    transpiler = TranspilerService()
    validation = await transpiler.validate(request.yaml_content)

    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML configuration: {', '.join(validation.get('errors', []))}"
        )

    # Update fields
    config.name = request.name
    config.description = request.description
    config.yaml_content = request.yaml_content
    config.image_type = request.image_type.value
    config.fedora_version = request.fedora_version
    config.enable_plymouth = request.enable_plymouth

    await db.commit()
    await db.refresh(config)

    return config


@router.delete("/{config_id}", status_code=204)
async def delete_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """
    Delete a configuration.
    """
    result = await db.execute(
        select(ConfigModel).where(ConfigModel.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration {config_id} not found")

    await db.delete(config)
    await db.commit()

    return None

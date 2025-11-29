"""
Configuration Router
====================

Endpoints for YAML configuration management and transpilation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import yaml

from ..database import get_db, ConfigModel
from ..models import (
    ConfigValidateRequest, ConfigValidateResponse,
    ConfigTranspileRequest, ConfigTranspileResponse,
    ConfigCreateRequest, ConfigResponse, ConfigListResponse,
    YamlDefinitionFile, YamlDefinitionsListResponse
)
from ..services.transpiler_service import TranspilerService
from ..config import settings

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
        raise HTTPException(
            status_code=400,
            detail=f"Transpilation failed: {str(e)}"
        ) from e


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
        raise HTTPException(
            status_code=409,
            detail=f"Configuration '{request.name}' already exists"
        )

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


@router.post("/upsert", response_model=ConfigResponse)
async def upsert_config(
    request: ConfigCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create or update a configuration (idempotent upsert).

    If a configuration with the given name exists, it will be updated.
    If it doesn't exist, a new configuration will be created.

    This operation is idempotent - calling it multiple times with the
    same data will result in the same final state.
    """
    # Check if config already exists
    result = await db.execute(
        select(ConfigModel).where(ConfigModel.name == request.name)
    )
    existing = result.scalar_one_or_none()

    # Validate YAML before creating/updating
    transpiler = TranspilerService()
    validation = await transpiler.validate(request.yaml_content)

    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML configuration: {', '.join(validation.get('errors', []))}"
        )

    if existing:
        # Update existing config
        existing.description = request.description
        existing.yaml_content = request.yaml_content
        existing.image_type = request.image_type.value
        existing.fedora_version = request.fedora_version
        existing.enable_plymouth = request.enable_plymouth

        await db.commit()
        await db.refresh(existing)

        return existing
    else:
        # Create new config
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


@router.get("/definitions/list", response_model=YamlDefinitionsListResponse)
async def list_yaml_definitions():
    """
    List available YAML definition files from the yaml-definitions directory.

    Returns metadata about each YAML file including name, description, and image type.
    """
    definitions_dir = settings.YAML_DEFINITIONS_DIR

    if not definitions_dir.exists():
        return YamlDefinitionsListResponse(definitions=[], total=0)

    definitions = []

    # Find all .yml and .yaml files
    for yaml_file in definitions_dir.glob("*.y*ml"):
        try:
            with open(yaml_file, 'r') as f:
                content = yaml.safe_load(f)

            definition = YamlDefinitionFile(
                filename=yaml_file.name,
                name=content.get('name', yaml_file.stem),
                description=content.get('description'),
                image_type=content.get('image-type'),
                path=str(yaml_file.relative_to(settings.REPO_ROOT))
            )
            definitions.append(definition)
        except Exception as e:
            # Skip files that can't be parsed
            continue

    return YamlDefinitionsListResponse(
        definitions=definitions,
        total=len(definitions)
    )


@router.get("/definitions/{filename}")
async def get_yaml_definition(filename: str):
    """
    Get the content of a specific YAML definition file.

    Returns the raw YAML content for use in builds or editing.
    """
    definitions_dir = settings.YAML_DEFINITIONS_DIR

    # Security: prevent directory traversal
    if '..' in filename or '/' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    yaml_file = definitions_dir / filename

    if not yaml_file.exists():
        raise HTTPException(status_code=404, detail=f"Definition file '{filename}' not found")

    try:
        with open(yaml_file, 'r') as f:
            content = f.read()
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read definition file: {str(e)}"
        ) from e

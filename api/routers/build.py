"""
Build Router
============

Endpoints for triggering builds and tracking build status.
"""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import yaml

from ..database import get_db, ConfigModel, BuildModel, async_session_maker
from ..models import (
    BuildTriggerRequest, BuildResponse, BuildStatusResponse,
    BuildListResponse, BuildStatus
)
from ..services.github_service import GitHubService
from ..services.transpiler_service import TranspilerService
from ..config import settings
from ..auth import current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(current_active_user)])


async def poll_build_status(build_id: int, workflow_run_id: int, max_polls: int = 120):
    """
    Background task to poll GitHub workflow status and update build.

    Args:
        build_id: Build ID to update
        workflow_run_id: GitHub workflow run ID
        max_polls: Maximum number of polling attempts (default: 120 = 1 hour at 30s intervals)
    """
    logger.info(f"Starting status polling for build {build_id}, workflow {workflow_run_id}")

    github = GitHubService(settings.GITHUB_TOKEN, settings.GITHUB_REPO)
    poll_count = 0

    while poll_count < max_polls:
        try:
            # Sleep first to give workflow time to start
            await asyncio.sleep(30)  # Poll every 30 seconds
            poll_count += 1

            # Get workflow status
            workflow_run = await github.get_workflow_run(workflow_run_id)

            logger.info(
                f"Build {build_id} poll {poll_count}/{max_polls}: "
                f"status={workflow_run.status}, conclusion={workflow_run.conclusion}"
            )

            # Update build status in database
            async with async_session_maker() as db:
                result = await db.execute(
                    select(BuildModel).where(BuildModel.id == build_id)
                )
                build = result.scalar_one_or_none()

                if not build:
                    logger.error(f"Build {build_id} not found during polling")
                    return

                # Check if workflow completed
                if workflow_run.status == "completed":
                    if workflow_run.conclusion == "success":
                        build.status = BuildStatus.SUCCESS
                    elif workflow_run.conclusion in ["failure", "cancelled", "timed_out"]:
                        build.status = BuildStatus.FAILURE
                    elif workflow_run.conclusion == "cancelled":
                        build.status = BuildStatus.CANCELLED
                    else:
                        build.status = BuildStatus.FAILURE

                    build.completed_at = datetime.utcnow()
                    await db.commit()

                    logger.info(
                        f"Build {build_id} completed: {build.status.value} "
                        f"(conclusion: {workflow_run.conclusion})"
                    )
                    return  # Stop polling

                # Still in progress, continue polling
                if build.status != BuildStatus.IN_PROGRESS:
                    build.status = BuildStatus.IN_PROGRESS
                    await db.commit()

        except Exception as e:
            logger.error(f"Error polling build {build_id}: {e}", exc_info=True)
            # Continue polling despite errors
            continue

    # Max polls reached
    logger.warning(f"Build {build_id} reached max polling attempts ({max_polls})")


@router.post("/trigger", response_model=BuildResponse, status_code=202)
async def trigger_build(
    request: BuildTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger a new build via GitHub Actions (direct integration).

    Can trigger from:
    - A saved configuration (config_id)
    - Ad-hoc YAML content (yaml_content)
    - A yaml-definition file (definition_filename)

    The build is triggered directly via GitHub API and a background task
    polls for status updates.
    """
    yaml_content = None
    config_id = request.config_id
    yaml_config_file = None  # For GitHub workflow input

    # Get YAML content from config, definition file, or request
    if config_id:
        result = await db.execute(
            select(ConfigModel).where(ConfigModel.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail=f"Configuration {config_id} not found")

        yaml_content = config.yaml_content
        image_type = config.image_type
        fedora_version = config.fedora_version
        enable_plymouth = config.enable_plymouth
    elif request.definition_filename:
        # Load YAML from yaml-definitions directory
        from pathlib import Path

        # Security: prevent directory traversal
        if '..' in request.definition_filename or '/' in request.definition_filename:
            raise HTTPException(status_code=400, detail="Invalid definition filename")

        definition_path = settings.YAML_DEFINITIONS_DIR / request.definition_filename

        if not definition_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Definition file '{request.definition_filename}' not found"
            )

        try:
            with open(definition_path, 'r') as f:
                yaml_content = f.read()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read definition file: {str(e)}"
            ) from e

        # Use the filename for GitHub workflow
        yaml_config_file = f"yaml-definitions/{request.definition_filename}"
        image_type = request.image_type.value
        fedora_version = request.fedora_version
        enable_plymouth = request.enable_plymouth
    elif request.yaml_content:
        yaml_content = request.yaml_content
        image_type = request.image_type.value
        fedora_version = request.fedora_version
        enable_plymouth = request.enable_plymouth
    else:
        raise HTTPException(
            status_code=400,
            detail="Either config_id, yaml_content, or definition_filename must be provided"
        )

    # Validate YAML
    transpiler = TranspilerService()
    validation = await transpiler.validate(yaml_content)

    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML: {', '.join(validation.get('errors', []))}"
        )

    # Create build record
    build = BuildModel(
        config_id=config_id,
        status=BuildStatus.QUEUED,
        image_type=image_type,
        fedora_version=fedora_version,
        ref=request.ref
    )

    db.add(build)
    await db.commit()
    await db.refresh(build)

    # Trigger GitHub workflow directly
    try:
        if not settings.GITHUB_TOKEN:
            raise HTTPException(
                status_code=503,
                detail="GitHub token not configured. Set GITHUB_TOKEN environment variable."
            )

        github = GitHubService(settings.GITHUB_TOKEN, settings.GITHUB_REPO)

        # Build workflow inputs
        workflow_inputs = {
            "image_type": image_type,
            "distro_version": fedora_version,
            "enable_plymouth": str(enable_plymouth).lower()
        }

        # Include yaml_config_file if using a definition file
        if yaml_config_file:
            workflow_inputs["yaml_config_file"] = yaml_config_file

        logger.info(
            f"Triggering GitHub workflow for build {build.id}: "
            f"image_type={image_type}, version={fedora_version}, ref={request.ref}"
        )

        # Trigger workflow
        workflow_run = await github.trigger_workflow(
            workflow_file=settings.GITHUB_WORKFLOW_FILE,
            ref=request.ref,
            inputs=workflow_inputs
        )

        if not workflow_run:
            raise HTTPException(
                status_code=500,
                detail="Failed to get workflow run information after triggering"
            )

        # Update build with workflow run ID
        build.workflow_run_id = workflow_run.id
        build.status = BuildStatus.IN_PROGRESS
        build.started_at = datetime.utcnow()
        await db.commit()
        await db.refresh(build)

        logger.info(
            f"Build {build.id} triggered successfully: workflow_run_id={workflow_run.id}"
        )

        # Start background task to poll for status
        background_tasks.add_task(poll_build_status, build.id, workflow_run.id)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to trigger build {build.id}: {e}", exc_info=True)
        build.status = BuildStatus.FAILURE
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger GitHub workflow: {str(e)}"
        ) from e

    return build


@router.get("/{build_id}/status", response_model=BuildStatusResponse)
async def get_build_status(build_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get detailed build status including GitHub workflow status.
    """
    result = await db.execute(
        select(BuildModel).where(BuildModel.id == build_id)
    )
    build = result.scalar_one_or_none()

    if not build:
        raise HTTPException(status_code=404, detail=f"Build {build_id} not found")

    # Get GitHub workflow status if available
    workflow_status = None
    workflow_url = None
    conclusion = None
    logs_url = None

    if build.workflow_run_id and settings.GITHUB_TOKEN:
        try:
            github_service = GitHubService(settings.GITHUB_TOKEN, settings.GITHUB_REPO)
            workflow_run = await github_service.get_workflow_run(build.workflow_run_id)

            workflow_status = workflow_run.status
            workflow_url = workflow_run.html_url
            conclusion = workflow_run.conclusion
            logs_url = f"{workflow_run.html_url}/checks"

            # Update build status based on workflow
            if workflow_run.conclusion == "success":
                build.status = BuildStatus.SUCCESS
                build.completed_at = datetime.utcnow()
            elif workflow_run.conclusion in ["failure", "cancelled", "timed_out"]:
                build.status = BuildStatus.FAILURE
                build.completed_at = datetime.utcnow()

            await db.commit()
            await db.refresh(build)

        except Exception:
            # Log error but don't fail the request
            pass

    return BuildStatusResponse(
        build=build,
        workflow_status=workflow_status,
        workflow_url=workflow_url,
        conclusion=conclusion,
        logs_url=logs_url
    )


@router.get("/", response_model=BuildListResponse)
async def list_builds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: BuildStatus = None,
    config_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List builds with pagination and filtering.
    """
    # Build query
    query = select(BuildModel)

    if status:
        query = query.where(BuildModel.status == status)

    if config_id:
        query = query.where(BuildModel.config_id == config_id)

    # Get total count
    count_query = select(func.count(BuildModel.id))
    if status:
        count_query = count_query.where(BuildModel.status == status)
    if config_id:
        count_query = count_query.where(BuildModel.config_id == config_id)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Get paginated builds
    offset = (page - 1) * page_size
    result = await db.execute(
        query
        .order_by(BuildModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    builds = result.scalars().all()

    return BuildListResponse(
        builds=builds,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/{build_id}/cancel", response_model=BuildResponse)
async def cancel_build(build_id: int, db: AsyncSession = Depends(get_db)):
    """
    Cancel a running build.
    """
    result = await db.execute(
        select(BuildModel).where(BuildModel.id == build_id)
    )
    build = result.scalar_one_or_none()

    if not build:
        raise HTTPException(status_code=404, detail=f"Build {build_id} not found")

    if build.status not in [BuildStatus.QUEUED, BuildStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel build in status: {build.status}"
        )

    # Cancel GitHub workflow if available
    if build.workflow_run_id and settings.GITHUB_TOKEN:
        try:
            github_service = GitHubService(settings.GITHUB_TOKEN, settings.GITHUB_REPO)
            await github_service.cancel_workflow_run(build.workflow_run_id)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to cancel GitHub workflow: {str(e)}"
            ) from e

    # Update build status
    build.status = BuildStatus.CANCELLED
    build.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(build)

    return build

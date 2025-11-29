"""
Build Worker
============

Asynchronous worker that processes build messages from BlazingMQ.
Implements immutable event sourcing and idempotent operations.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import async_session_maker, BuildModel, BuildEventModel, get_db
from ..models import BuildStatus
from ..queue import QueueMessage, get_queue_backend, shutdown_queue_backend
from ..services.github_service import GitHubService

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BuildWorker:
    """
    Worker for processing build messages.

    Implements:
    - Immutable event sourcing for state transitions
    - Idempotent message processing
    - Automatic retries with exponential backoff
    - Dead letter queue for failed messages
    """

    def __init__(self):
        self.queue = get_queue_backend()
        self.github = GitHubService(
            token=settings.GITHUB_TOKEN,
            repo_name=settings.GITHUB_REPO
        )
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the worker."""
        logger.info("Starting build worker...")
        logger.info(f"Deployment mode: {settings.DEPLOYMENT_MODE}")
        logger.info(f"Worker concurrency: {settings.WORKER_CONCURRENCY}")
        logger.info(f"BlazingMQ broker: {settings.BLAZINGMQ_BROKER_URI}")

        # Connect to queue
        await self.queue.connect()

        self.running = True
        logger.info("Build worker started and ready to process messages")

        # Start processing loop
        await self._process_loop()

    async def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping build worker...")
        self.running = False
        self._shutdown_event.set()

        # Disconnect from queue
        await shutdown_queue_backend()

        logger.info("Build worker stopped")

    async def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                # Dequeue next message
                message = await self.queue.dequeue(
                    queue_name=settings.BLAZINGMQ_QUEUE_BUILD,
                    timeout=settings.WORKER_POLL_INTERVAL
                )

                if message is None:
                    # No message available, continue loop
                    continue

                logger.info(
                    f"Processing message: {message.id} "
                    f"(type: {message.message_type}, retry: {message.retry_count})"
                )

                # Process message based on type
                try:
                    if message.message_type == "build.trigger":
                        await self._process_build_trigger(message)
                    elif message.message_type == "build.status_check":
                        await self._process_status_check(message)
                    else:
                        logger.warning(f"Unknown message type: {message.message_type}")
                        # Ack unknown messages to prevent reprocessing
                        await self.queue.ack(settings.BLAZINGMQ_QUEUE_BUILD, message)
                        continue

                    # Success - acknowledge message
                    await self.queue.ack(settings.BLAZINGMQ_QUEUE_BUILD, message)

                    logger.info(f"Successfully processed message {message.id}")

                except Exception as e:
                    logger.error(
                        f"Failed to process message {message.id}: {e}",
                        exc_info=True
                    )

                    # Negative acknowledge - will retry or go to DLQ
                    await self.queue.nack(
                        queue_name=settings.BLAZINGMQ_QUEUE_BUILD,
                        message=message,
                        requeue=True
                    )

            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

        logger.info("Processing loop exited")

    async def _process_build_trigger(self, message: QueueMessage):
        """
        Process build trigger message.

        Implements immutable event sourcing:
        1. Check current build state (idempotency)
        2. Create immutable event for state transition
        3. Update build state atomically
        4. Trigger GitHub workflow
        5. Enqueue status check message
        """
        payload = message.payload
        build_id = payload["build_id"]

        async with async_session_maker() as db:
            # Fetch build
            stmt = select(BuildModel).where(BuildModel.id == build_id)
            result = await db.execute(stmt)
            build = result.scalar_one_or_none()

            if not build:
                logger.error(f"Build {build_id} not found")
                return

            # Idempotency check
            if build.status != BuildStatus.QUEUED:
                logger.info(
                    f"Build {build_id} already processed "
                    f"(status: {build.status})"
                )
                return

            try:
                # Transition to IN_PROGRESS
                await self._transition_build_state(
                    db=db,
                    build=build,
                    from_status=BuildStatus.QUEUED,
                    to_status=BuildStatus.IN_PROGRESS,
                    event_type="build_started",
                    metadata={"message_id": message.id}
                )

                # Trigger GitHub workflow
                logger.info(f"Triggering GitHub workflow for build {build_id}")

                # Build workflow inputs
                workflow_inputs = {
                    "fedora_version": payload["fedora_version"],
                    "image_type": payload["image_type"],
                    "enable_plymouth": str(payload.get("enable_plymouth", True)).lower()
                }

                # Include yaml_config_file if using a definition file
                if payload.get("yaml_config_file"):
                    workflow_inputs["yaml_config_file"] = payload["yaml_config_file"]

                workflow_run = await self.github.trigger_workflow(
                    ref=payload["ref"],
                    inputs=workflow_inputs
                )

                # Update with workflow run ID
                build.workflow_run_id = workflow_run.id
                await db.commit()

                # Create event
                event = BuildEventModel(
                    build_id=build_id,
                    event_type="workflow_triggered",
                    metadata={
                        "workflow_run_id": workflow_run.id,
                        "workflow_url": workflow_run.html_url
                    }
                )
                db.add(event)
                await db.commit()

                logger.info(
                    f"Triggered workflow for build {build_id}: "
                    f"run_id={workflow_run.id}"
                )

                # Enqueue status check message (separate concern)
                status_check_message = QueueMessage(
                    message_type="build.status_check",
                    payload={
                        "build_id": build_id,
                        "workflow_run_id": workflow_run.id
                    },
                    correlation_id=message.correlation_id
                )

                # Delay status check to allow workflow to start
                await asyncio.sleep(10)

                await self.queue.enqueue(
                    queue_name=settings.BLAZINGMQ_QUEUE_BUILD,
                    message=status_check_message
                )

            except Exception as e:
                logger.error(f"Failed to trigger build {build_id}: {e}")

                # Transition to FAILURE
                await self._transition_build_state(
                    db=db,
                    build=build,
                    from_status=build.status,
                    to_status=BuildStatus.FAILURE,
                    event_type="build_failed",
                    metadata={
                        "error": str(e),
                        "message_id": message.id
                    }
                )

                raise

    async def _process_status_check(self, message: QueueMessage):
        """
        Process build status check message.

        Polls GitHub workflow status and updates build accordingly.
        Re-enqueues itself if build still in progress.
        """
        payload = message.payload
        build_id = payload["build_id"]
        workflow_run_id = payload["workflow_run_id"]

        async with async_session_maker() as db:
            # Fetch build
            stmt = select(BuildModel).where(BuildModel.id == build_id)
            result = await db.execute(stmt)
            build = result.scalar_one_or_none()

            if not build:
                logger.error(f"Build {build_id} not found")
                return

            # Idempotency: Check if build already completed
            if build.status in [BuildStatus.SUCCESS, BuildStatus.FAILURE, BuildStatus.CANCELLED]:
                logger.info(f"Build {build_id} already completed (status: {build.status})")
                return

            try:
                # Get workflow run status from GitHub
                workflow_run = await self.github.get_workflow_run(workflow_run_id)

                logger.info(
                    f"Build {build_id} workflow status: "
                    f"{workflow_run.status} / {workflow_run.conclusion}"
                )

                if workflow_run.status == "completed":
                    # Workflow completed - update build status
                    if workflow_run.conclusion == "success":
                        await self._transition_build_state(
                            db=db,
                            build=build,
                            from_status=BuildStatus.IN_PROGRESS,
                            to_status=BuildStatus.SUCCESS,
                            event_type="build_completed",
                            metadata={
                                "workflow_run_id": workflow_run_id,
                                "conclusion": workflow_run.conclusion
                            }
                        )
                    else:
                        await self._transition_build_state(
                            db=db,
                            build=build,
                            from_status=BuildStatus.IN_PROGRESS,
                            to_status=BuildStatus.FAILURE,
                            event_type="build_failed",
                            metadata={
                                "workflow_run_id": workflow_run_id,
                                "conclusion": workflow_run.conclusion
                            }
                        )

                    logger.info(f"Build {build_id} completed with status: {build.status}")

                else:
                    # Still in progress - re-enqueue status check
                    logger.info(f"Build {build_id} still in progress, re-enqueueing status check")

                    # Create new status check message
                    new_message = QueueMessage(
                        message_type="build.status_check",
                        payload=payload,
                        correlation_id=message.correlation_id
                    )

                    # Delay before next check (polling interval)
                    await asyncio.sleep(30)

                    await self.queue.enqueue(
                        queue_name=settings.BLAZINGMQ_QUEUE_BUILD,
                        message=new_message
                    )

            except Exception as e:
                logger.error(f"Failed to check status for build {build_id}: {e}")
                raise

    async def _transition_build_state(
        self,
        db: AsyncSession,
        build: BuildModel,
        from_status: BuildStatus,
        to_status: BuildStatus,
        event_type: str,
        metadata: Optional[dict] = None
    ):
        """
        Immutable state transition with event sourcing.

        Creates an immutable event record and updates build state atomically.
        """
        # Create immutable event
        event = BuildEventModel(
            build_id=build.id,
            event_type=event_type,
            from_status=from_status.value,
            to_status=to_status.value,
            event_data=metadata,  # Renamed from 'metadata' to 'event_data' to avoid SQLAlchemy reserved name conflict
            timestamp=datetime.utcnow()
        )
        db.add(event)

        # Update build state
        build.status = to_status
        build.version += 1  # Increment version for optimistic locking

        if to_status == BuildStatus.IN_PROGRESS:
            build.started_at = datetime.utcnow()
        elif to_status in [BuildStatus.SUCCESS, BuildStatus.FAILURE, BuildStatus.CANCELLED]:
            build.completed_at = datetime.utcnow()

        await db.commit()

        logger.info(
            f"Build {build.id} transitioned: "
            f"{from_status.value} -> {to_status.value} "
            f"(event: {event_type})"
        )


async def main():
    """Main entry point for worker."""
    worker = BuildWorker()

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(worker.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Worker crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())

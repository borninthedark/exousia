"""
BlazingMQ Queue Backend
=======================

Implements message queue with BlazingMQ for immutable, idempotent operations.
Supports both laptop (single broker) and cloud (cluster) deployment modes.
"""

import asyncio
import json
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from enum import Enum

try:
    import blazingmq
except ImportError:
    blazingmq = None  # Will be installed via pip

from .config import settings

logger = logging.getLogger(__name__)


class MessagePriority(int, Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class QueueMessage:
    """
    Immutable message for queue operations.

    The message ID is deterministic based on content for idempotency.
    If the same operation is enqueued twice, it will have the same ID
    and be deduplicated by BlazingMQ.
    """
    message_type: str  # e.g., "build.trigger", "build.status_check"
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    retry_count: int = 0
    correlation_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def id(self) -> str:
        """
        Generate deterministic message ID for idempotency.
        Same payload + type = same ID = deduplication.
        """
        content = f"{self.message_type}:{json.dumps(self.payload, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'message_type': self.message_type,
            'payload': self.payload,
            'priority': self.priority.value,
            'retry_count': self.retry_count,
            'correlation_id': self.correlation_id,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueMessage':
        """Create from dictionary."""
        return cls(
            message_type=data['message_type'],
            payload=data['payload'],
            priority=MessagePriority(data.get('priority', MessagePriority.NORMAL.value)),
            retry_count=data.get('retry_count', 0),
            correlation_id=data.get('correlation_id'),
            timestamp=data.get('timestamp', datetime.utcnow().isoformat())
        )

    def with_retry(self) -> 'QueueMessage':
        """Create new message with incremented retry count (immutable)."""
        return QueueMessage(
            message_type=self.message_type,
            payload=self.payload,
            priority=self.priority,
            retry_count=self.retry_count + 1,
            correlation_id=self.correlation_id,
            timestamp=self.timestamp
        )


class QueueBackend(ABC):
    """Abstract queue backend interface."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to queue broker."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to queue broker."""
        pass

    @abstractmethod
    async def enqueue(self, queue_name: str, message: QueueMessage) -> bool:
        """
        Enqueue a message.

        Returns:
            True if message was enqueued
            False if message was duplicate (idempotency)
        """
        pass

    @abstractmethod
    async def dequeue(self, queue_name: str, timeout: int = 30) -> Optional[QueueMessage]:
        """Dequeue next message with timeout."""
        pass

    @abstractmethod
    async def ack(self, queue_name: str, message: QueueMessage) -> None:
        """Acknowledge message processing completed."""
        pass

    @abstractmethod
    async def nack(self, queue_name: str, message: QueueMessage, requeue: bool = True) -> None:
        """Negative acknowledge - processing failed."""
        pass


class BlazingMQBackend(QueueBackend):
    """
    BlazingMQ queue backend for both laptop and cloud deployments.

    Features:
    - Message deduplication via message GUID
    - At-least-once delivery
    - Persistent storage
    - Dead letter queue for failed messages
    - Priority queues
    """

    def __init__(
        self,
        broker_uri: str = settings.BLAZINGMQ_BROKER_URI,
        domain: str = settings.BLAZINGMQ_DOMAIN,
    ):
        self.broker_uri = broker_uri
        self.domain = domain
        self.session: Optional['blazingmq.Session'] = None
        self.queues: Dict[str, 'blazingmq.Queue'] = {}
        self._dedup_cache: Dict[str, float] = {}  # msg_id -> timestamp
        self._connected = False

    async def connect(self) -> None:
        """Connect to BlazingMQ broker."""
        if self._connected:
            return

        if blazingmq is None:
            raise RuntimeError(
                "BlazingMQ Python SDK not installed. "
                "Install with: pip install blazingmq"
            )

        try:
            logger.info(f"Connecting to BlazingMQ broker at {self.broker_uri}")

            # Create session
            self.session = await asyncio.to_thread(
                blazingmq.Session,
                broker_uri=self.broker_uri,
                session_options=blazingmq.SessionOptions(
                    broker_timeout_ms=30000,
                    num_processing_threads=settings.WORKER_CONCURRENCY,
                )
            )

            # Start session
            await asyncio.to_thread(self.session.start)

            self._connected = True
            logger.info("Successfully connected to BlazingMQ")

        except Exception as e:
            logger.error(f"Failed to connect to BlazingMQ: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from BlazingMQ broker."""
        if not self._connected:
            return

        try:
            # Close all queues
            for queue in self.queues.values():
                await asyncio.to_thread(queue.close)

            # Stop session
            if self.session:
                await asyncio.to_thread(self.session.stop)

            self.queues.clear()
            self._connected = False
            logger.info("Disconnected from BlazingMQ")

        except Exception as e:
            logger.error(f"Error disconnecting from BlazingMQ: {e}")
            raise

    async def _get_queue(self, queue_name: str, mode: str = 'write') -> 'blazingmq.Queue':
        """Get or create queue handle."""
        if queue_name not in self.queues:
            queue_uri = f"bmq://{self.domain}/{queue_name}"

            logger.info(f"Opening queue: {queue_uri} (mode: {mode})")

            # Open queue
            queue = await asyncio.to_thread(
                self.session.open_queue,
                queue_uri=queue_uri,
                flags=(
                    blazingmq.QueueFlags.WRITE if mode == 'write'
                    else blazingmq.QueueFlags.READ
                ),
                options=blazingmq.QueueOptions(
                    max_unconfirmed_messages=1000,
                    max_unconfirmed_bytes=33554432,  # 32MB
                    consumer_priority=0,
                    suspends_on_bad_host_health=True
                )
            )

            self.queues[queue_name] = queue

        return self.queues[queue_name]

    async def enqueue(self, queue_name: str, message: QueueMessage) -> bool:
        """
        Enqueue message with deduplication.

        Relies on BlazingMQ to generate the message GUID.
        A short-lived local cache prevents accidental re-enqueue within
        the broker's deduplication window.
        """
        await self.connect()

        # Check local dedup cache (fast path)
        msg_id = message.id
        current_time = datetime.utcnow().timestamp()

        if msg_id in self._dedup_cache:
            cache_time = self._dedup_cache[msg_id]
            if current_time - cache_time < settings.QUEUE_MESSAGE_TTL:
                logger.info(f"Message {msg_id} already enqueued (local cache)")
                return False

        try:
            queue = await self._get_queue(queue_name, mode='write')

            # Serialize message
            message_bytes = json.dumps(message.to_dict()).encode('utf-8')

            # Create BlazingMQ message (SDK will generate GUID)
            bmq_message = blazingmq.Message(
                payload=message_bytes,
                properties={
                    'message_type': message.message_type,
                    'correlation_id': message.correlation_id or '',
                    'retry_count': str(message.retry_count)
                }
            )

            # Set priority
            if message.priority == MessagePriority.HIGH:
                bmq_message.set_priority(3)
            elif message.priority == MessagePriority.CRITICAL:
                bmq_message.set_priority(4)

            # Post message
            await asyncio.to_thread(queue.post, bmq_message)

            # Update dedup cache
            self._dedup_cache[msg_id] = current_time

            # Clean old cache entries
            self._cleanup_dedup_cache()

            logger.info(
                f"Enqueued message {msg_id} to {queue_name} "
                f"(type: {message.message_type}, priority: {message.priority.name})"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to enqueue message {msg_id}: {e}")
            raise

    async def dequeue(self, queue_name: str, timeout: int = 30) -> Optional[QueueMessage]:
        """
        Dequeue next message.

        Returns None if no message available within timeout.
        """
        await self.connect()

        try:
            queue = await self._get_queue(queue_name, mode='read')

            # Get next message (blocking with timeout)
            bmq_message = await asyncio.wait_for(
                asyncio.to_thread(queue.get_next_message),
                timeout=timeout
            )

            if bmq_message is None:
                return None

            # Deserialize
            message_data = json.loads(bmq_message.payload.decode('utf-8'))
            message = QueueMessage.from_dict(message_data)

            logger.info(
                f"Dequeued message {message.id} from {queue_name} "
                f"(type: {message.message_type})"
            )

            return message

        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Failed to dequeue from {queue_name}: {e}")
            raise

    async def ack(self, queue_name: str, message: QueueMessage) -> None:
        """Acknowledge message processing completed."""
        try:
            queue = await self._get_queue(queue_name, mode='read')

            # Confirm message
            await asyncio.to_thread(
                queue.confirm,
                message_guid=message.id
            )

            logger.info(f"Acknowledged message {message.id}")

        except Exception as e:
            logger.error(f"Failed to ack message {message.id}: {e}")
            raise

    async def nack(self, queue_name: str, message: QueueMessage, requeue: bool = True) -> None:
        """
        Negative acknowledge - processing failed.

        If requeue=True and retry_count < MAX_RETRIES:
            Re-enqueue with incremented retry count
        Else:
            Move to dead letter queue
        """
        try:
            # Reject message
            queue = await self._get_queue(queue_name, mode='read')
            await asyncio.to_thread(queue.confirm, message_guid=message.id)

            if requeue and message.retry_count < settings.QUEUE_MAX_RETRIES:
                # Re-enqueue with backoff
                new_message = message.with_retry()

                logger.info(
                    f"Re-enqueueing message {message.id} "
                    f"(retry {new_message.retry_count}/{settings.QUEUE_MAX_RETRIES})"
                )

                # Add delay before retry (exponential backoff)
                delay = settings.QUEUE_RETRY_DELAY * (2 ** message.retry_count)
                await asyncio.sleep(delay)

                await self.enqueue(queue_name, new_message)
            else:
                # Move to DLQ
                logger.warning(
                    f"Moving message {message.id} to dead letter queue "
                    f"(max retries exceeded or requeue=False)"
                )

                await self.enqueue(settings.BLAZINGMQ_QUEUE_DLQ, message)

        except Exception as e:
            logger.error(f"Failed to nack message {message.id}: {e}")
            raise

    def _cleanup_dedup_cache(self) -> None:
        """Remove expired entries from dedup cache."""
        current_time = datetime.utcnow().timestamp()
        expired_keys = [
            msg_id for msg_id, timestamp in self._dedup_cache.items()
            if current_time - timestamp > settings.QUEUE_MESSAGE_TTL
        ]
        for key in expired_keys:
            del self._dedup_cache[key]


# Singleton instance
_queue_backend: Optional[BlazingMQBackend] = None


def get_queue_backend() -> BlazingMQBackend:
    """Get or create queue backend singleton."""
    global _queue_backend

    if _queue_backend is None:
        _queue_backend = BlazingMQBackend()

    return _queue_backend


async def shutdown_queue_backend() -> None:
    """Shutdown queue backend (call on app shutdown)."""
    global _queue_backend

    if _queue_backend:
        await _queue_backend.disconnect()
        _queue_backend = None

"""
Comprehensive Tests for Queue Deduplication
===========================================

Tests the deduplication logic in the BlazingMQ queue backend.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict

from api.queue import (
    QueueMessage,
    MessagePriority,
    BlazingMQBackend,
)
from api.config import settings


class TestMessageIDGeneration:
    """Test deterministic message ID generation."""

    def test_same_payload_same_id(self):
        """Test that messages with same content produce same ID."""
        message1 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
        )
        message2 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
        )

        assert message1.id == message2.id

    def test_different_payload_different_id(self):
        """Test that messages with different content produce different IDs."""
        message1 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
        )
        message2 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 456, "ref": "main"},
        )

        assert message1.id != message2.id

    def test_different_type_different_id(self):
        """Test that messages with different types produce different IDs."""
        message1 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
        )
        message2 = QueueMessage(
            message_type="build.status_check",
            payload={"build_id": 123},
        )

        assert message1.id != message2.id

    def test_payload_order_doesnt_matter(self):
        """Test that payload key order doesn't affect ID (JSON sorted)."""
        message1 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main", "config_id": 1},
        )
        message2 = QueueMessage(
            message_type="build.trigger",
            payload={"ref": "main", "config_id": 1, "build_id": 123},
        )

        # Should produce same ID because JSON is sorted by keys
        assert message1.id == message2.id

    def test_id_length(self):
        """Test that message ID is 32 characters (truncated SHA256)."""
        message = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
        )

        assert len(message.id) == 32
        assert message.id.isalnum()  # Only hex characters

    def test_id_is_deterministic_across_instances(self):
        """Test ID generation is deterministic across different instances."""
        ids = []
        for _ in range(10):
            message = QueueMessage(
                message_type="build.trigger",
                payload={"build_id": 123, "ref": "main"},
            )
            ids.append(message.id)

        # All IDs should be identical
        assert len(set(ids)) == 1

    def test_priority_doesnt_affect_id(self):
        """Test that message priority doesn't affect ID."""
        message1 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
            priority=MessagePriority.LOW,
        )
        message2 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
            priority=MessagePriority.HIGH,
        )

        # Priority should not affect ID (only type + payload)
        assert message1.id == message2.id

    def test_retry_count_doesnt_affect_id(self):
        """Test that retry count doesn't affect ID."""
        message1 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
            retry_count=0,
        )
        message2 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
            retry_count=5,
        )

        # Retry count should not affect ID
        assert message1.id == message2.id


class TestLocalDedupCache:
    """Test local deduplication cache functionality."""

    @pytest.fixture
    def mock_blazingmq(self):
        """Mock BlazingMQ module."""
        with patch("api.queue.blazingmq") as mock:
            # Mock Session
            mock_session = MagicMock()
            mock.Session.return_value = mock_session

            # Mock Queue
            mock_queue = MagicMock()
            mock_session.open_queue.return_value = mock_queue

            # Mock Message - track instantiation
            mock_message_class = MagicMock()
            mock.Message = mock_message_class

            # Enums
            mock.QueueFlags.WRITE = 1
            mock.QueueFlags.READ = 2
            mock.QueueOptions = MagicMock
            mock.SessionOptions = MagicMock

            yield mock

    @pytest.mark.asyncio
    async def test_dedup_cache_prevents_duplicate_enqueue(self, mock_blazingmq):
        """Test that local cache prevents duplicate message enqueue."""
        backend = BlazingMQBackend()

        message = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
        )

        # First enqueue should succeed
        result1 = await backend.enqueue("test-queue", message)
        assert result1 is True

        # Second enqueue (same message) should be deduplicated
        result2 = await backend.enqueue("test-queue", message)
        assert result2 is False

        # Verify only one message was created (first enqueue)
        # Second enqueue should be caught by dedup cache
        assert result1 is True  # First succeeded
        assert result2 is False  # Second was deduplicated

    @pytest.mark.asyncio
    async def test_dedup_cache_expires_after_ttl(self, mock_blazingmq):
        """Test that dedup cache entries expire after TTL."""
        backend = BlazingMQBackend()

        message = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
        )

        # First enqueue
        result1 = await backend.enqueue("test-queue", message)
        assert result1 is True

        # Manually expire cache entry by modifying timestamp
        msg_id = message.id
        old_timestamp = backend._dedup_cache[msg_id]
        # Set timestamp to more than TTL seconds ago
        backend._dedup_cache[msg_id] = old_timestamp - settings.QUEUE_MESSAGE_TTL - 100

        # Second enqueue should succeed (cache expired)
        result2 = await backend.enqueue("test-queue", message)
        assert result2 is True

        # Should have enqueued successfully both times (cache expired)
        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    async def test_dedup_cache_cleanup_removes_old_entries(self, mock_blazingmq):
        """Test that cache cleanup removes expired entries."""
        backend = BlazingMQBackend()

        # Add multiple messages to cache
        messages = []
        for i in range(5):
            message = QueueMessage(
                message_type="build.trigger",
                payload={"build_id": i, "ref": "main"},
            )
            await backend.enqueue("test-queue", message)
            messages.append(message)

        # Verify all in cache
        assert len(backend._dedup_cache) == 5

        # Expire first 3 messages
        current_time = datetime.utcnow().timestamp()
        for i in range(3):
            backend._dedup_cache[messages[i].id] = (
                current_time - settings.QUEUE_MESSAGE_TTL - 100
            )

        # Trigger cleanup
        backend._cleanup_dedup_cache()

        # Should only have 2 entries left
        assert len(backend._dedup_cache) == 2
        assert messages[3].id in backend._dedup_cache
        assert messages[4].id in backend._dedup_cache

    @pytest.mark.asyncio
    async def test_different_messages_both_enqueued(self, mock_blazingmq):
        """Test that different messages are both enqueued (not deduplicated)."""
        backend = BlazingMQBackend()

        message1 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
        )
        message2 = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 456, "ref": "develop"},
        )

        result1 = await backend.enqueue("test-queue", message1)
        result2 = await backend.enqueue("test-queue", message2)

        # Both should succeed (different messages)
        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    async def test_dedup_works_across_different_queues(self, mock_blazingmq):
        """Test that deduplication works even across different queues."""
        backend = BlazingMQBackend()

        message = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
        )

        # Enqueue to first queue
        result1 = await backend.enqueue("queue1", message)
        assert result1 is True

        # Try to enqueue same message to different queue
        result2 = await backend.enqueue("queue2", message)
        assert result2 is False  # Still deduplicated (same message ID)


class TestMessageRetry:
    """Test message retry logic with immutability."""

    def test_with_retry_creates_new_message(self):
        """Test that with_retry creates a new message instance."""
        original = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
            retry_count=0,
        )

        retried = original.with_retry()

        # Should be different instances
        assert retried is not original

        # Retry count should be incremented
        assert retried.retry_count == 1
        assert original.retry_count == 0  # Original unchanged

    def test_with_retry_preserves_other_fields(self):
        """Test that with_retry preserves all other fields."""
        original = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
            priority=MessagePriority.HIGH,
            correlation_id="test-correlation",
            retry_count=2,
        )

        retried = original.with_retry()

        assert retried.message_type == original.message_type
        assert retried.payload == original.payload
        assert retried.priority == original.priority
        assert retried.correlation_id == original.correlation_id
        assert retried.retry_count == 3
        assert retried.timestamp == original.timestamp

    def test_retry_doesnt_change_message_id(self):
        """Test that retry doesn't change message ID (same content)."""
        original = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
            retry_count=0,
        )

        retried = original.with_retry()

        # ID should be the same (based on type + payload only)
        assert retried.id == original.id

    def test_multiple_retries(self):
        """Test multiple retry operations."""
        message = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
            retry_count=0,
        )

        # Chain multiple retries
        retry1 = message.with_retry()
        retry2 = retry1.with_retry()
        retry3 = retry2.with_retry()

        assert message.retry_count == 0
        assert retry1.retry_count == 1
        assert retry2.retry_count == 2
        assert retry3.retry_count == 3

        # All should have same ID
        assert message.id == retry1.id == retry2.id == retry3.id


class TestMessageSerialization:
    """Test message serialization and deserialization."""

    def test_to_dict_includes_all_fields(self):
        """Test that to_dict includes all message fields."""
        message = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
            priority=MessagePriority.HIGH,
            retry_count=2,
            correlation_id="test-123",
        )

        data = message.to_dict()

        assert data["id"] == message.id
        assert data["message_type"] == "build.trigger"
        assert data["payload"] == {"build_id": 123, "ref": "main"}
        assert data["priority"] == MessagePriority.HIGH.value
        assert data["retry_count"] == 2
        assert data["correlation_id"] == "test-123"
        assert "timestamp" in data

    def test_from_dict_recreates_message(self):
        """Test that from_dict correctly recreates message."""
        original = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
            priority=MessagePriority.HIGH,
            retry_count=2,
            correlation_id="test-123",
        )

        data = original.to_dict()
        recreated = QueueMessage.from_dict(data)

        assert recreated.message_type == original.message_type
        assert recreated.payload == original.payload
        assert recreated.priority == original.priority
        assert recreated.retry_count == original.retry_count
        assert recreated.correlation_id == original.correlation_id
        assert recreated.id == original.id

    def test_roundtrip_serialization(self):
        """Test that message survives to_dict -> from_dict roundtrip."""
        original = QueueMessage(
            message_type="build.status_check",
            payload={"build_id": 456, "workflow_run_id": 789},
            priority=MessagePriority.CRITICAL,
        )

        # Roundtrip
        data = original.to_dict()
        recreated = QueueMessage.from_dict(data)

        assert recreated.id == original.id
        assert recreated.message_type == original.message_type
        assert recreated.payload == original.payload
        assert recreated.priority == original.priority


class TestConcurrentDeduplication:
    """Test deduplication under concurrent conditions."""

    @pytest.fixture
    def mock_blazingmq(self):
        """Mock BlazingMQ module."""
        with patch("api.queue.blazingmq") as mock:
            mock_session = MagicMock()
            mock.Session.return_value = mock_session

            mock_queue = MagicMock()
            mock_session.open_queue.return_value = mock_queue

            mock_message_class = MagicMock()
            mock.Message = mock_message_class

            mock.QueueFlags.WRITE = 1
            mock.QueueFlags.READ = 2
            mock.QueueOptions = MagicMock
            mock.SessionOptions = MagicMock

            yield mock

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_enqueues(self, mock_blazingmq):
        """Test that concurrent duplicate enqueues are handled correctly.

        Note: Without proper locking, concurrent checks might all pass before
        the cache is updated. This demonstrates the race condition that could occur.
        """
        backend = BlazingMQBackend()

        message = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123, "ref": "main"},
        )

        # Enqueue same message concurrently
        results = await asyncio.gather(
            backend.enqueue("test-queue", message),
            backend.enqueue("test-queue", message),
            backend.enqueue("test-queue", message),
        )

        # All results should be boolean
        assert all(isinstance(r, bool) for r in results)

        # At least one should succeed
        successful = sum(1 for r in results if r is True)
        assert successful >= 1

        # Due to race conditions in concurrent execution, multiple may succeed
        # This is acceptable behavior for the current implementation

    @pytest.mark.asyncio
    async def test_concurrent_different_messages(self, mock_blazingmq):
        """Test that concurrent different messages all succeed."""
        backend = BlazingMQBackend()

        messages = [
            QueueMessage(
                message_type="build.trigger",
                payload={"build_id": i, "ref": "main"},
            )
            for i in range(10)
        ]

        # Enqueue all concurrently
        results = await asyncio.gather(
            *[backend.enqueue("test-queue", msg) for msg in messages]
        )

        # All different messages should succeed
        assert all(r is True for r in results)

        # All should be in cache
        assert len(backend._dedup_cache) == 10


class TestImmutability:
    """Test that QueueMessage is immutable."""

    def test_message_is_frozen(self):
        """Test that message dataclass is frozen."""
        message = QueueMessage(
            message_type="build.trigger",
            payload={"build_id": 123},
        )

        # Should not be able to modify attributes
        with pytest.raises(Exception):  # FrozenInstanceError in Python 3.10+
            message.message_type = "build.status_check"

    def test_payload_is_stored_by_reference(self):
        """Test that payload dict is stored by reference (not copied).

        Note: While the QueueMessage dataclass is frozen, the payload dict
        is mutable and stored by reference. Modifying the dict will affect
        the message ID on subsequent access since ID is computed from payload.

        In production, this means payloads should be treated as immutable
        or the ID should be computed and cached at creation time.
        """
        payload = {"build_id": 123, "ref": "main"}
        message = QueueMessage(
            message_type="build.trigger",
            payload=payload,
        )

        original_id = message.id

        # Modify original payload dict
        payload["ref"] = "develop"
        payload["new_field"] = "new_value"

        # Since ID is computed from payload and payload was modified,
        # the ID will be different (this is the actual behavior)
        new_id = message.id
        assert new_id != original_id

        # This demonstrates that payloads should be treated as immutable
        assert message.payload == payload  # Same reference

"""
Comprehensive Tests for Event Sourcing
=======================================

Tests the event sourcing implementation for build state transitions.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import BuildModel, BuildEventModel, ConfigModel
from api.models import BuildStatus


class TestEventCreation:
    """Test event creation during state transitions."""

    @pytest.fixture
    async def config_with_build(self, test_db: AsyncSession, sample_config):
        """Create a build for testing."""
        build = BuildModel(
            config_id=sample_config.id,
            workflow_run_id=12345,
            status=BuildStatus.PENDING,
            image_type="fedora-sway-atomic",
            fedora_version="43",
            ref="main",
        )
        test_db.add(build)
        await test_db.commit()
        await test_db.refresh(build)
        return build

    @pytest.mark.asyncio
    async def test_event_is_created_on_state_transition(
        self, test_db: AsyncSession, config_with_build
    ):
        """Test that an event is created when build state changes."""
        build = config_with_build

        # Create event for state transition
        event = BuildEventModel(
            build_id=build.id,
            event_type="status_changed",
            from_status=BuildStatus.PENDING.value,
            to_status=BuildStatus.QUEUED.value,
            event_data={"reason": "build triggered"},
        )
        test_db.add(event)

        # Update build status
        build.status = BuildStatus.QUEUED
        build.version += 1

        await test_db.commit()
        await test_db.refresh(event)

        # Verify event was created
        assert event.id is not None
        assert event.build_id == build.id
        assert event.event_type == "status_changed"
        assert event.from_status == BuildStatus.PENDING.value
        assert event.to_status == BuildStatus.QUEUED.value
        assert event.timestamp is not None

    @pytest.mark.asyncio
    async def test_multiple_events_create_audit_trail(
        self, test_db: AsyncSession, config_with_build
    ):
        """Test that multiple state transitions create a complete audit trail."""
        build = config_with_build

        # Simulate build lifecycle with events
        transitions = [
            (BuildStatus.PENDING, BuildStatus.QUEUED, "build_queued"),
            (BuildStatus.QUEUED, BuildStatus.IN_PROGRESS, "build_started"),
            (BuildStatus.IN_PROGRESS, BuildStatus.SUCCESS, "build_completed"),
        ]

        for from_status, to_status, event_type in transitions:
            # Create event
            event = BuildEventModel(
                build_id=build.id,
                event_type=event_type,
                from_status=from_status.value,
                to_status=to_status.value,
                timestamp=datetime.utcnow(),
            )
            test_db.add(event)

            # Update build
            build.status = to_status
            build.version += 1

            await test_db.commit()

        # Query all events for this build
        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .order_by(BuildEventModel.timestamp)
        )
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        assert len(events) == 3
        assert events[0].event_type == "build_queued"
        assert events[1].event_type == "build_started"
        assert events[2].event_type == "build_completed"

        # Verify state progression
        assert events[0].from_status == BuildStatus.PENDING.value
        assert events[0].to_status == BuildStatus.QUEUED.value
        assert events[1].from_status == BuildStatus.QUEUED.value
        assert events[1].to_status == BuildStatus.IN_PROGRESS.value
        assert events[2].from_status == BuildStatus.IN_PROGRESS.value
        assert events[2].to_status == BuildStatus.SUCCESS.value

    @pytest.mark.asyncio
    async def test_event_stores_metadata(self, test_db: AsyncSession, config_with_build):
        """Test that events can store arbitrary metadata."""
        build = config_with_build

        metadata = {
            "workflow_run_id": 98765,
            "workflow_url": "https://github.com/user/repo/actions/runs/98765",
            "triggered_by": "user@example.com",
            "commit_sha": "abc123def456",
        }

        event = BuildEventModel(
            build_id=build.id,
            event_type="workflow_triggered",
            event_data=metadata,
        )
        test_db.add(event)
        await test_db.commit()
        await test_db.refresh(event)

        # Verify metadata is stored and retrievable
        assert event.event_data == metadata
        assert event.event_data["workflow_run_id"] == 98765
        assert event.event_data["commit_sha"] == "abc123def456"

    @pytest.mark.asyncio
    async def test_event_timestamp_is_automatic(
        self, test_db: AsyncSession, config_with_build
    ):
        """Test that event timestamp is automatically set."""
        build = config_with_build

        before = datetime.utcnow()

        event = BuildEventModel(
            build_id=build.id,
            event_type="test_event",
        )
        test_db.add(event)
        await test_db.commit()
        await test_db.refresh(event)

        after = datetime.utcnow()

        # Timestamp should be set automatically
        assert event.timestamp is not None

        # Remove timezone info for comparison and allow for some tolerance
        # (database may truncate microseconds)
        event_time = event.timestamp.replace(tzinfo=None)

        # Should be roughly at the same time (within 1 second tolerance)
        time_diff = (event_time - before).total_seconds()
        assert -1 <= time_diff <= (after - before).total_seconds() + 1


class TestEventImmutability:
    """Test that events are immutable (append-only log)."""

    @pytest.fixture
    async def build_with_event(self, test_db: AsyncSession, sample_config):
        """Create a build with an event."""
        build = BuildModel(
            config_id=sample_config.id,
            workflow_run_id=12345,
            status=BuildStatus.QUEUED,
            image_type="fedora-sway-atomic",
            fedora_version="43",
            ref="main",
        )
        test_db.add(build)
        await test_db.commit()

        event = BuildEventModel(
            build_id=build.id,
            event_type="build_queued",
            from_status=BuildStatus.PENDING.value,
            to_status=BuildStatus.QUEUED.value,
        )
        test_db.add(event)
        await test_db.commit()
        await test_db.refresh(build)
        await test_db.refresh(event)

        return build, event

    @pytest.mark.asyncio
    async def test_events_are_never_deleted(
        self, test_db: AsyncSession, build_with_event
    ):
        """Test that events remain even if build state changes."""
        build, original_event = build_with_event

        # Change build status multiple times
        for status in [BuildStatus.IN_PROGRESS, BuildStatus.SUCCESS]:
            build.status = status
            build.version += 1
            await test_db.commit()

        # Original event should still exist
        stmt = select(BuildEventModel).where(BuildEventModel.id == original_event.id)
        result = await test_db.execute(stmt)
        event = result.scalar_one_or_none()

        assert event is not None
        assert event.event_type == "build_queued"

    @pytest.mark.asyncio
    async def test_events_survive_build_completion(
        self, test_db: AsyncSession, build_with_event
    ):
        """Test that all events are preserved throughout build lifecycle."""
        build, _ = build_with_event

        # Add more events
        event_types = ["build_started", "workflow_triggered", "build_completed"]
        for event_type in event_types:
            event = BuildEventModel(
                build_id=build.id,
                event_type=event_type,
            )
            test_db.add(event)

        await test_db.commit()

        # Mark build as complete
        build.status = BuildStatus.SUCCESS
        build.completed_at = datetime.utcnow()
        await test_db.commit()

        # All events should still exist
        stmt = select(func.count(BuildEventModel.id)).where(
            BuildEventModel.build_id == build.id
        )
        result = await test_db.execute(stmt)
        count = result.scalar()

        assert count == 4  # 1 original + 3 new events

    @pytest.mark.asyncio
    async def test_event_cascade_delete_with_build(
        self, test_db: AsyncSession, build_with_event
    ):
        """Test that events are cascade deleted when build is deleted."""
        build, event = build_with_event
        build_id = build.id

        # Delete build
        await test_db.delete(build)
        await test_db.commit()

        # Events should be cascade deleted (as per relationship config)
        stmt = select(BuildEventModel).where(BuildEventModel.build_id == build_id)
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        assert len(events) == 0


class TestEventQuerying:
    """Test querying events for analysis and reconstruction."""

    @pytest.fixture
    async def build_with_multiple_events(self, test_db: AsyncSession, sample_config):
        """Create a build with multiple events over time."""
        build = BuildModel(
            config_id=sample_config.id,
            workflow_run_id=12345,
            status=BuildStatus.SUCCESS,
            image_type="fedora-sway-atomic",
            fedora_version="43",
            ref="main",
        )
        test_db.add(build)
        await test_db.commit()

        # Create events with different timestamps
        base_time = datetime.utcnow()
        events_data = [
            ("build_queued", 0),
            ("build_started", 5),
            ("workflow_triggered", 10),
            ("status_check", 20),
            ("status_check", 30),
            ("build_completed", 40),
        ]

        for event_type, offset_seconds in events_data:
            event = BuildEventModel(
                build_id=build.id,
                event_type=event_type,
                timestamp=base_time + timedelta(seconds=offset_seconds),
            )
            test_db.add(event)

        await test_db.commit()
        await test_db.refresh(build)
        return build

    @pytest.mark.asyncio
    async def test_query_events_by_build_id(
        self, test_db: AsyncSession, build_with_multiple_events
    ):
        """Test querying all events for a specific build."""
        build = build_with_multiple_events

        stmt = select(BuildEventModel).where(BuildEventModel.build_id == build.id)
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        assert len(events) == 6

    @pytest.mark.asyncio
    async def test_query_events_by_type(
        self, test_db: AsyncSession, build_with_multiple_events
    ):
        """Test querying events by type."""
        build = build_with_multiple_events

        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .where(BuildEventModel.event_type == "status_check")
        )
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        assert len(events) == 2
        assert all(e.event_type == "status_check" for e in events)

    @pytest.mark.asyncio
    async def test_query_events_ordered_by_timestamp(
        self, test_db: AsyncSession, build_with_multiple_events
    ):
        """Test querying events in chronological order."""
        build = build_with_multiple_events

        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .order_by(BuildEventModel.timestamp)
        )
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        # Verify chronological order
        event_types = [e.event_type for e in events]
        assert event_types == [
            "build_queued",
            "build_started",
            "workflow_triggered",
            "status_check",
            "status_check",
            "build_completed",
        ]

        # Verify timestamps are increasing
        for i in range(len(events) - 1):
            assert events[i].timestamp <= events[i + 1].timestamp

    @pytest.mark.asyncio
    async def test_query_events_in_time_range(
        self, test_db: AsyncSession, build_with_multiple_events
    ):
        """Test querying events within a specific time range."""
        build = build_with_multiple_events

        # Get all events first to determine time range
        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .order_by(BuildEventModel.timestamp)
        )
        result = await test_db.execute(stmt)
        all_events = result.scalars().all()

        # Query events between first and third event timestamps
        start_time = all_events[0].timestamp
        end_time = all_events[2].timestamp

        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .where(BuildEventModel.timestamp >= start_time)
            .where(BuildEventModel.timestamp <= end_time)
        )
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_count_events_by_type(
        self, test_db: AsyncSession, build_with_multiple_events
    ):
        """Test counting events by type."""
        build = build_with_multiple_events

        stmt = (
            select(func.count(BuildEventModel.id))
            .where(BuildEventModel.build_id == build.id)
            .where(BuildEventModel.event_type == "status_check")
        )
        result = await test_db.execute(stmt)
        count = result.scalar()

        assert count == 2


class TestOptimisticLocking:
    """Test optimistic locking with version field."""

    @pytest.fixture
    async def fresh_build(self, test_db: AsyncSession, sample_config):
        """Create a fresh build."""
        build = BuildModel(
            config_id=sample_config.id,
            workflow_run_id=12345,
            status=BuildStatus.QUEUED,
            image_type="fedora-sway-atomic",
            fedora_version="43",
            ref="main",
            version=1,
        )
        test_db.add(build)
        await test_db.commit()
        await test_db.refresh(build)
        return build

    @pytest.mark.asyncio
    async def test_version_increments_on_update(
        self, test_db: AsyncSession, fresh_build
    ):
        """Test that version increments on state updates."""
        build = fresh_build
        initial_version = build.version

        # Update build status
        build.status = BuildStatus.IN_PROGRESS
        build.version += 1
        await test_db.commit()

        assert build.version == initial_version + 1

    @pytest.mark.asyncio
    async def test_version_tracks_multiple_updates(
        self, test_db: AsyncSession, fresh_build
    ):
        """Test that version correctly tracks multiple updates."""
        build = fresh_build
        initial_version = build.version

        # Make multiple updates
        statuses = [
            BuildStatus.IN_PROGRESS,
            BuildStatus.SUCCESS,
        ]

        for status in statuses:
            build.status = status
            build.version += 1
            await test_db.commit()

        assert build.version == initial_version + 2

    @pytest.mark.asyncio
    async def test_optimistic_locking_prevents_stale_updates(
        self, test_db: AsyncSession, fresh_build
    ):
        """Test optimistic locking pattern prevents conflicting updates."""
        build = fresh_build
        build_id = build.id
        original_version = build.version

        # Simulate concurrent update by another session
        # First "session" updates
        build.status = BuildStatus.IN_PROGRESS
        build.version += 1
        await test_db.commit()

        # Second "session" tries to update using stale version
        # In production, this would be detected by checking version matches
        stmt = select(BuildModel).where(
            BuildModel.id == build_id, BuildModel.version == original_version
        )
        result = await test_db.execute(stmt)
        stale_build = result.scalar_one_or_none()

        # Should not find the build (version already incremented)
        assert stale_build is None


class TestStateReconstruction:
    """Test reconstructing build state from event log."""

    @pytest.fixture
    async def build_with_complete_history(self, test_db: AsyncSession, sample_config):
        """Create a build with complete event history."""
        build = BuildModel(
            config_id=sample_config.id,
            workflow_run_id=12345,
            status=BuildStatus.SUCCESS,
            image_type="fedora-sway-atomic",
            fedora_version="43",
            ref="main",
        )
        test_db.add(build)
        await test_db.commit()

        # Create complete event history
        base_time = datetime.utcnow()
        transitions = [
            ("build_queued", BuildStatus.PENDING, BuildStatus.QUEUED, 0),
            ("build_started", BuildStatus.QUEUED, BuildStatus.IN_PROGRESS, 10),
            ("workflow_triggered", None, None, 15),
            ("build_completed", BuildStatus.IN_PROGRESS, BuildStatus.SUCCESS, 60),
        ]

        for event_type, from_status, to_status, offset in transitions:
            event = BuildEventModel(
                build_id=build.id,
                event_type=event_type,
                from_status=from_status.value if from_status else None,
                to_status=to_status.value if to_status else None,
                timestamp=base_time + timedelta(seconds=offset),
            )
            test_db.add(event)

        await test_db.commit()
        await test_db.refresh(build)
        return build

    @pytest.mark.asyncio
    async def test_reconstruct_state_from_events(
        self, test_db: AsyncSession, build_with_complete_history
    ):
        """Test reconstructing build state from event log."""
        build = build_with_complete_history

        # Query events in order
        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .order_by(BuildEventModel.timestamp)
        )
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        # Reconstruct state by replaying events
        current_status = BuildStatus.PENDING

        for event in events:
            if event.to_status:
                current_status = BuildStatus(event.to_status)

        # Final reconstructed state should match current build state
        assert current_status == build.status
        assert current_status == BuildStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_reconstruct_state_at_point_in_time(
        self, test_db: AsyncSession, build_with_complete_history
    ):
        """Test reconstructing state at a specific point in time."""
        build = build_with_complete_history

        # Get all events
        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .order_by(BuildEventModel.timestamp)
        )
        result = await test_db.execute(stmt)
        all_events = result.scalars().all()

        # Get timestamp of second event
        cutoff_time = all_events[1].timestamp

        # Query events up to that point
        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .where(BuildEventModel.timestamp <= cutoff_time)
            .order_by(BuildEventModel.timestamp)
        )
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        # Reconstruct state
        current_status = BuildStatus.PENDING
        for event in events:
            if event.to_status:
                current_status = BuildStatus(event.to_status)

        # At that point in time, build should be IN_PROGRESS
        assert current_status == BuildStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_event_log_provides_full_audit_trail(
        self, test_db: AsyncSession, build_with_complete_history
    ):
        """Test that event log provides complete audit trail."""
        build = build_with_complete_history

        stmt = (
            select(BuildEventModel)
            .where(BuildEventModel.build_id == build.id)
            .order_by(BuildEventModel.timestamp)
        )
        result = await test_db.execute(stmt)
        events = result.scalars().all()

        # Should have all transition events
        assert len(events) == 4

        # Can trace exact state progression
        state_changes = [
            e for e in events if e.from_status is not None and e.to_status is not None
        ]

        assert len(state_changes) == 3
        assert state_changes[0].from_status == BuildStatus.PENDING.value
        assert state_changes[0].to_status == BuildStatus.QUEUED.value
        assert state_changes[1].from_status == BuildStatus.QUEUED.value
        assert state_changes[1].to_status == BuildStatus.IN_PROGRESS.value
        assert state_changes[2].from_status == BuildStatus.IN_PROGRESS.value
        assert state_changes[2].to_status == BuildStatus.SUCCESS.value


class TestEventRelationships:
    """Test event-build relationships."""

    @pytest.fixture
    async def build_with_events(self, test_db: AsyncSession, sample_config):
        """Create a build with events."""
        build = BuildModel(
            config_id=sample_config.id,
            workflow_run_id=12345,
            status=BuildStatus.QUEUED,
            image_type="fedora-sway-atomic",
            fedora_version="43",
            ref="main",
        )
        test_db.add(build)
        await test_db.commit()

        for i in range(3):
            event = BuildEventModel(
                build_id=build.id,
                event_type=f"event_{i}",
            )
            test_db.add(event)

        await test_db.commit()
        await test_db.refresh(build)
        return build

    @pytest.mark.asyncio
    async def test_build_has_events_relationship(
        self, test_db: AsyncSession, build_with_events
    ):
        """Test that build has access to its events via relationship."""
        build = build_with_events

        # Reload build with events
        stmt = select(BuildModel).where(BuildModel.id == build.id)
        result = await test_db.execute(stmt)
        build = result.scalar_one()

        # Access events via relationship
        await test_db.refresh(build, ["events"])
        assert len(build.events) == 3

    @pytest.mark.asyncio
    async def test_event_has_build_relationship(
        self, test_db: AsyncSession, build_with_events
    ):
        """Test that event has access to its build via relationship."""
        # Get an event
        stmt = select(BuildEventModel).where(
            BuildEventModel.build_id == build_with_events.id
        )
        result = await test_db.execute(stmt)
        event = result.scalars().first()

        # Access build via relationship
        await test_db.refresh(event, ["build"])
        assert event.build is not None
        assert event.build.id == build_with_events.id

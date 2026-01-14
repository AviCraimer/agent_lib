"""Tests for Fanouts parallel task coordination."""

# pyright: reportPrivateUsage=false
# Tests need access to Store internals (_fanouts) to verify behavior.

from __future__ import annotations

import pytest

from agent_lib.store.Fanouts import FanoutResult, TaskResult
from agent_lib.store.Store import Store


class TestFanoutCreation:
    """Tests for creating fanouts."""

    def test_create_fanout_initializes_registry(self) -> None:
        """Creating a fanout sets up registry with pending tasks."""
        store = Store()
        completed: list[FanoutResult] = []

        store._fanouts.create(
            fanout_id="batch_1",
            fanout_description="Test batch",
            task_names=["task_a", "task_b"],
            on_complete=lambda r: completed.append(r),
        )

        assert "batch_1" in store._fanouts.registry
        assert "task_a" in store._fanouts.registry["batch_1"]
        assert "task_b" in store._fanouts.registry["batch_1"]
        assert not store._fanouts.registry["batch_1"]["task_a"].resolved

    def test_create_duplicate_fanout_raises(self) -> None:
        """Creating a fanout with existing ID raises ValueError."""
        store = Store()

        store._fanouts.create("batch_1", "First batch", ["task_a"], lambda r: None)

        with pytest.raises(ValueError, match="already exists"):
            store._fanouts.create("batch_1", "Duplicate", ["task_b"], lambda r: None)


class TestMakeResolver:
    """Tests for make_resolver factory."""

    def test_make_resolver_returns_callable(self) -> None:
        """make_resolver returns a callable that resolves the task."""
        store = Store()
        store._fanouts.create("batch_1", "Test", ["task_a"], lambda r: None)

        resolver = store._fanouts.make_resolver("batch_1", "task_a")

        assert callable(resolver)

    def test_make_resolver_unknown_fanout_raises(self) -> None:
        """make_resolver with unknown fanout_id raises ValueError."""
        store = Store()

        with pytest.raises(ValueError, match="does not exist"):
            store._fanouts.make_resolver("unknown", "task_a")

    def test_make_resolver_unknown_task_raises(self) -> None:
        """make_resolver with unknown task_name raises ValueError."""
        store = Store()
        store._fanouts.create("batch_1", "Test", ["task_a"], lambda r: None)

        with pytest.raises(ValueError, match="not in fanout"):
            store._fanouts.make_resolver("batch_1", "unknown_task")


class TestTaskResolution:
    """Tests for resolving tasks via resolver."""

    def test_resolve_task_updates_registry(self) -> None:
        """Calling resolver updates the task status in registry."""
        store = Store()
        store._fanouts.create("batch_1", "Test", ["task_a"], lambda r: None)
        resolver = store._fanouts.make_resolver("batch_1", "task_a")

        resolver(TaskResult(resolved=True, success=True, result="done"))

        status = store._fanouts.registry["batch_1"]["task_a"]
        assert status.resolved is True
        assert status.success is True
        assert status.result == "done"

    def test_resolve_task_failure(self) -> None:
        """Resolving with failure stores failure info."""
        store = Store()
        store._fanouts.create("batch_1", "Test", ["task_a"], lambda r: None)
        resolver = store._fanouts.make_resolver("batch_1", "task_a")

        resolver(TaskResult(resolved=True, success=False, result="timeout error"))

        status = store._fanouts.registry["batch_1"]["task_a"]
        assert status.resolved is True
        assert status.success is False
        assert status.result == "timeout error"

    def test_resolve_already_resolved_raises(self) -> None:
        """Resolving an already resolved task raises RuntimeError."""
        store = Store()
        store._fanouts.create("batch_1", "Test", ["task_a"], lambda r: None)
        resolver = store._fanouts.make_resolver("batch_1", "task_a")

        resolver(TaskResult(resolved=True, success=True))

        with pytest.raises(RuntimeError, match="already resolved"):
            resolver(TaskResult(resolved=True, success=True))


class TestFanoutCompletion:
    """Tests for fanout completion callback."""

    def test_completion_fires_when_all_resolved(self) -> None:
        """on_complete fires when all tasks are resolved."""
        store = Store()
        completed: list[FanoutResult] = []

        store._fanouts.create(
            "batch_1",
            "Test batch",
            ["task_a", "task_b"],
            lambda r: completed.append(r),
        )

        resolver_a = store._fanouts.make_resolver("batch_1", "task_a")
        resolver_b = store._fanouts.make_resolver("batch_1", "task_b")

        resolver_a(TaskResult(resolved=True, success=True, result="result_a"))
        assert len(completed) == 0  # Not complete yet

        resolver_b(TaskResult(resolved=True, success=True, result="result_b"))
        assert len(completed) == 1  # Now complete

    def test_completion_result_contains_all_data(self) -> None:
        """FanoutResult contains all task data and counts."""
        store = Store()
        result_holder: list[FanoutResult] = []

        store._fanouts.create(
            "batch_1",
            "Multi-task batch",
            ["task_a", "task_b", "task_c"],
            lambda r: result_holder.append(r),
        )

        store._fanouts.make_resolver("batch_1", "task_a")(
            TaskResult(resolved=True, success=True, result="a_result")
        )
        store._fanouts.make_resolver("batch_1", "task_b")(
            TaskResult(resolved=True, success=False, result="failed: timeout")
        )
        store._fanouts.make_resolver("batch_1", "task_c")(
            TaskResult(resolved=True, success=True, result="c_result")
        )

        result = result_holder[0]
        assert result.fanout_id == "batch_1"
        assert result.fanout_description == "Multi-task batch"
        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.all_succeeded is False
        assert result.tasks["task_a"].result == "a_result"
        assert result.tasks["task_c"].result == "c_result"

    def test_completion_all_succeeded_property(self) -> None:
        """all_succeeded is True only when all tasks succeed."""
        store = Store()
        result_holder: list[FanoutResult] = []

        store._fanouts.create(
            "batch_1",
            "Success batch",
            ["task_a", "task_b"],
            lambda r: result_holder.append(r),
        )

        store._fanouts.make_resolver("batch_1", "task_a")(
            TaskResult(resolved=True, success=True)
        )
        store._fanouts.make_resolver("batch_1", "task_b")(
            TaskResult(resolved=True, success=True)
        )

        assert result_holder[0].all_succeeded is True


class TestFanoutCleanup:
    """Tests for fanout cleanup after completion."""

    def test_subscriber_unsubscribed_after_completion(self) -> None:
        """Fanout unsubscribes its watcher after completion."""
        store = Store()
        initial_subscriber_count = len(store._subscribers)

        store._fanouts.create("batch_1", "Test", ["task_a"], lambda r: None)
        assert len(store._subscribers) == initial_subscriber_count + 1

        store._fanouts.make_resolver("batch_1", "task_a")(
            TaskResult(resolved=True, success=True)
        )
        assert len(store._subscribers) == initial_subscriber_count

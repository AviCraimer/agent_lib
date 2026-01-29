"""Tests for Store subscription and notification system with StoreUpdaters."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import pytest

from agent_lib.agent_app.AgentApp import AgentApp
from agent_lib.store.Store import Store
from agent_lib.store.StoreUpdater import StoreUpdater
from agent_lib.store.StoreUpdaterAsync import StoreUpdaterAsync
from agent_lib.util.json_utils import JSONSchema


# =============================================================================
# Test Fixtures
# =============================================================================


class HasData(Protocol):
    """Protocol for stores with data dict."""

    data: dict[str, Any]


@dataclass(frozen=True)
class SetPayload:
    """Payload for set action."""

    key: str
    value: str


async def _async_set_handler(store: HasData, payload: SetPayload) -> SetPayload:
    """Async handler that returns payload for on_success."""
    await asyncio.sleep(0.01)
    return payload


def _on_success(store: HasData, result: SetPayload) -> frozenset[str]:
    """Store the result."""
    store.data[result.key] = result.value
    return frozenset({f"data.{result.key}"})


set_async_updater: StoreUpdaterAsync[SetPayload, SetPayload, Any] = StoreUpdaterAsync(
    name="set_async",
    description="Set data asynchronously.",
    payload_json_schema=JSONSchema({}),
    async_handler=_async_set_handler,
    on_success=_on_success,
)


def _set_sync_handler(store: HasData, payload: SetPayload) -> frozenset[str]:
    """Set data synchronously."""
    store.data[payload.key] = payload.value
    return frozenset({f"data.{payload.key}"})


set_sync_updater: StoreUpdater[SetPayload, Any] = StoreUpdater(
    name="set_sync",
    description="Set data synchronously.",
    payload_json_schema=JSONSchema({}),
    updater=_set_sync_handler,
)


class NotificationTestStore(Store, HasData):
    """Test store with data dict."""

    data: dict[str, Any]

    def __init__(self) -> None:
        self.data = {}
        super().__init__()


class NotificationTestApp(AgentApp[NotificationTestStore]):
    """Test app for notification testing."""

    def __init__(self) -> None:
        store = NotificationTestStore()
        super().__init__(store)
        set_sync_updater.bind(self)
        set_async_updater.bind(self)


# =============================================================================
# Tests
# =============================================================================


class TestSubscribe:
    """Tests for AgentApp.subscribers basic functionality."""

    def test_subscribe_receives_affects_on_sync_updater(self) -> None:
        """Subscriber callback receives affects function when sync updater triggers change."""
        app = NotificationTestApp()
        notifications: list[bool] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            notifications.append(affects("data.name"))

        app.subscribers.append(on_change)
        set_sync_updater(SetPayload("name", "Alice"))

        assert len(notifications) == 1
        assert notifications[0] is True  # data.name was affected

    @pytest.mark.asyncio
    async def test_subscribe_receives_affects_on_async_updater(self) -> None:
        """Subscriber callback receives affects function when async updater triggers change."""
        app = NotificationTestApp()
        notifications: list[bool] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            notifications.append(affects("data.name"))

        app.subscribers.append(on_change)
        await set_async_updater(SetPayload("name", "Bob"))

        assert len(notifications) == 1
        assert notifications[0] is True  # data.name was affected


class TestUnsubscribe:
    """Tests for unsubscribe functionality."""

    def test_unsubscribe_stops_callbacks(self) -> None:
        """After unsubscribe, callback is no longer called."""
        app = NotificationTestApp()
        call_count = 0

        def callback(_: Callable[[str], bool]) -> None:
            nonlocal call_count
            call_count += 1

        app.subscribers.append(callback)
        set_sync_updater(SetPayload("a", "1"))
        assert call_count == 1

        app.subscribers.remove(callback)
        set_sync_updater(SetPayload("b", "2"))
        assert call_count == 1  # unchanged

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_async_callbacks(self) -> None:
        """After unsubscribe, callback not called for async updaters."""
        app = NotificationTestApp()
        call_count = 0

        def callback(_: Callable[[str], bool]) -> None:
            nonlocal call_count
            call_count += 1

        app.subscribers.append(callback)
        await set_async_updater(SetPayload("a", "1"))
        assert call_count == 1

        app.subscribers.remove(callback)
        await set_async_updater(SetPayload("b", "2"))
        assert call_count == 1  # unchanged


class TestMultipleSubscribers:
    """Tests for multiple subscriber behavior."""

    def test_multiple_subscribers_all_notified(self) -> None:
        """All subscribers receive the affects function."""
        app = NotificationTestApp()
        calls_1: list[bool] = []
        calls_2: list[bool] = []

        app.subscribers.append(lambda affects: calls_1.append(affects("data.key")))
        app.subscribers.append(lambda affects: calls_2.append(affects("data.key")))

        set_sync_updater(SetPayload("key", "value"))

        assert len(calls_1) == 1
        assert len(calls_2) == 1
        assert calls_1[0] is True
        assert calls_2[0] is True

    def test_unsubscribe_one_keeps_others(self) -> None:
        """Unsubscribing one subscriber doesn't affect others."""
        app = NotificationTestApp()
        calls_1: list[bool] = []
        calls_2: list[bool] = []

        def callback_1(_: Callable[[str], bool]) -> None:
            calls_1.append(True)

        def callback_2(_: Callable[[str], bool]) -> None:
            calls_2.append(True)

        app.subscribers.append(callback_1)
        app.subscribers.append(callback_2)

        set_sync_updater(SetPayload("a", "1"))
        assert len(calls_1) == 1
        assert len(calls_2) == 1

        app.subscribers.remove(callback_1)

        set_sync_updater(SetPayload("b", "2"))
        assert len(calls_1) == 1  # unchanged
        assert len(calls_2) == 2  # still receiving


class TestAffectsFunction:
    """Tests for the affects() helper function."""

    def test_affects_returns_true_for_changed_path(self) -> None:
        """affects() returns True for paths that were changed."""
        app = NotificationTestApp()
        results: list[bool] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            results.append(affects("data.name"))
            results.append(affects("data.other"))

        app.subscribers.append(on_change)
        set_sync_updater(SetPayload("name", "Alice"))

        assert results[0] is True  # data.name was changed
        assert results[1] is False  # data.other was not changed

    def test_affects_partial_path_match(self) -> None:
        """affects() matches partial paths."""
        app = NotificationTestApp()
        results: list[bool] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            results.append(affects("data"))  # broader path
            results.append(affects("name"))  # just the key name

        app.subscribers.append(on_change)
        set_sync_updater(SetPayload("name", "Alice"))

        assert results[0] is True  # "data" is in the path
        assert results[1] is True  # "name" is in the path

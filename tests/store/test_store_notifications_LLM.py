"""Tests for Store subscription and notification system."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import pytest

from agent_lib.store.AsyncAction import AsyncAction
from agent_lib.store.Store import Store


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


set_async_action = AsyncAction[HasData, SetPayload, SetPayload](
    handler=_async_set_handler,
    on_success=_on_success,
)


class NotificationTestStore(Store, HasData):
    """Test store with both sync and async actions."""

    data: dict[str, Any]
    set_async = set_async_action

    def __init__(self) -> None:
        self.data = {}
        super().__init__()

    @Store.action
    def set_sync(self, payload: SetPayload) -> frozenset[str]:
        self.data[payload.key] = payload.value
        return frozenset({f"data.{payload.key}"})


# =============================================================================
# Tests
# =============================================================================


class TestSubscribe:
    """Tests for Store.subscribe() basic functionality."""

    def test_subscribe_receives_affects_on_sync_action(self) -> None:
        """Subscriber callback receives affects function when sync action triggers change."""
        store = NotificationTestStore()
        notifications: list[bool] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            notifications.append(affects("data.name"))

        store.subscribe(on_change)
        store.set_sync(SetPayload("name", "Alice"))

        assert len(notifications) == 1
        assert notifications[0] is True  # data.name was affected

    @pytest.mark.asyncio
    async def test_subscribe_receives_affects_on_async_action(self) -> None:
        """Subscriber callback receives affects function when async action triggers change."""
        store = NotificationTestStore()
        notifications: list[bool] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            notifications.append(affects("data.name"))

        store.subscribe(on_change)
        await store.set_async(SetPayload("name", "Bob"))

        assert len(notifications) == 1
        assert notifications[0] is True  # data.name was affected


class TestUnsubscribe:
    """Tests for unsubscribe functionality."""

    def test_unsubscribe_stops_callbacks(self) -> None:
        """After unsubscribe, callback is no longer called."""
        store = NotificationTestStore()
        call_count = 0

        def callback(_: Callable[[str], bool]) -> None:
            nonlocal call_count
            call_count += 1

        unsubscribe = store.subscribe(callback)
        store.set_sync(SetPayload("a", "1"))
        assert call_count == 1

        unsubscribe()
        store.set_sync(SetPayload("b", "2"))
        assert call_count == 1  # unchanged

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_async_callbacks(self) -> None:
        """After unsubscribe, callback not called for async actions."""
        store = NotificationTestStore()
        call_count = 0

        def callback(_: Callable[[str], bool]) -> None:
            nonlocal call_count
            call_count += 1

        unsubscribe = store.subscribe(callback)
        await store.set_async(SetPayload("a", "1"))
        assert call_count == 1

        unsubscribe()
        await store.set_async(SetPayload("b", "2"))
        assert call_count == 1  # unchanged


class TestMultipleSubscribers:
    """Tests for multiple subscriber behavior."""

    def test_multiple_subscribers_all_notified(self) -> None:
        """All subscribers receive the affects function."""
        store = NotificationTestStore()
        calls_1: list[bool] = []
        calls_2: list[bool] = []

        store.subscribe(lambda affects: calls_1.append(affects("data.key")))
        store.subscribe(lambda affects: calls_2.append(affects("data.key")))

        store.set_sync(SetPayload("key", "value"))

        assert len(calls_1) == 1
        assert len(calls_2) == 1
        assert calls_1[0] is True
        assert calls_2[0] is True

    def test_unsubscribe_one_keeps_others(self) -> None:
        """Unsubscribing one subscriber doesn't affect others."""
        store = NotificationTestStore()
        calls_1: list[bool] = []
        calls_2: list[bool] = []

        unsub_1 = store.subscribe(lambda _: calls_1.append(True))
        store.subscribe(lambda _: calls_2.append(True))

        store.set_sync(SetPayload("a", "1"))
        assert len(calls_1) == 1
        assert len(calls_2) == 1

        unsub_1()

        store.set_sync(SetPayload("b", "2"))
        assert len(calls_1) == 1  # unchanged
        assert len(calls_2) == 2  # still receiving


class TestAffectsFunction:
    """Tests for the affects() helper function."""

    def test_affects_returns_true_for_changed_path(self) -> None:
        """affects() returns True for paths that were changed."""
        store = NotificationTestStore()
        results: list[bool] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            results.append(affects("data.name"))
            results.append(affects("data.other"))

        store.subscribe(on_change)
        store.set_sync(SetPayload("name", "Alice"))

        assert results[0] is True  # data.name was changed
        assert results[1] is False  # data.other was not changed

    def test_affects_partial_path_match(self) -> None:
        """affects() matches partial paths."""
        store = NotificationTestStore()
        results: list[bool] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            results.append(affects("data"))  # broader path
            results.append(affects("name"))  # just the key name

        store.subscribe(on_change)
        store.set_sync(SetPayload("name", "Alice"))

        assert results[0] is True  # "data" is in the path
        assert results[1] is True  # "name" is in the path

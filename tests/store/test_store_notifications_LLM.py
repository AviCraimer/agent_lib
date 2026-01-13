"""Tests for Store subscription and notification system."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

import pytest
from deepdiff import Delta

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

    def test_subscribe_receives_delta_on_sync_action(self) -> None:
        """Subscriber callback receives Delta when sync action triggers change."""
        store = NotificationTestStore()
        received: list[Delta] = []

        store.subscribe(lambda d: received.append(d))
        store.set_sync(SetPayload("name", "Alice"))

        assert len(received) == 1
        assert received[0].diff  # non-empty

    @pytest.mark.asyncio
    async def test_subscribe_receives_delta_on_async_action(self) -> None:
        """Subscriber callback receives Delta when async action triggers change."""
        store = NotificationTestStore()
        received: list[Delta] = []

        store.subscribe(lambda d: received.append(d))
        await store.set_async(SetPayload("name", "Bob"))

        assert len(received) == 1
        assert received[0].diff  # non-empty


class TestUnsubscribe:
    """Tests for unsubscribe functionality."""

    def test_unsubscribe_stops_callbacks(self) -> None:
        """After unsubscribe, callback is no longer called."""
        store = NotificationTestStore()
        call_count = 0

        def callback(_: Delta) -> None:
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

        def callback(_: Delta) -> None:
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
        """All subscribers receive the Delta."""
        store = NotificationTestStore()
        calls_1: list[Delta] = []
        calls_2: list[Delta] = []

        store.subscribe(lambda d: calls_1.append(d))
        store.subscribe(lambda d: calls_2.append(d))

        store.set_sync(SetPayload("key", "value"))

        assert len(calls_1) == 1
        assert len(calls_2) == 1
        assert calls_1[0].diff == calls_2[0].diff

    def test_unsubscribe_one_keeps_others(self) -> None:
        """Unsubscribing one subscriber doesn't affect others."""
        store = NotificationTestStore()
        calls_1: list[Delta] = []
        calls_2: list[Delta] = []

        unsub_1 = store.subscribe(lambda d: calls_1.append(d))
        store.subscribe(lambda d: calls_2.append(d))

        store.set_sync(SetPayload("a", "1"))
        assert len(calls_1) == 1
        assert len(calls_2) == 1

        unsub_1()

        store.set_sync(SetPayload("b", "2"))
        assert len(calls_1) == 1  # unchanged
        assert len(calls_2) == 2  # still receiving

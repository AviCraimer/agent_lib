"""Tests for AsyncAction instance pattern with Store.

Tests the pattern of creating AsyncAction instances separately and attaching
them as class attributes to Store subclasses, using Protocols for type safety.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

import pytest
from deepdiff import Delta

from agent_lib.store.AsyncAction import AsyncAction
from agent_lib.store.Store import Store


# =============================================================================
# Protocol Definition
# =============================================================================


class HasApiData(Protocol):
    """Protocol for stores that have an API key and data storage."""

    api_key: str
    data: dict[str, Any]


# =============================================================================
# Payload and Result Types
# =============================================================================


@dataclass(frozen=True)
class FetchPayload:
    """Payload for fetch_data action."""

    api_endpoint: str
    data_result_key: str


@dataclass
class FetchResult:
    """Result from successful fetch, includes key for storage."""

    key: str
    fetched_data: dict[str, Any]


class FetchError(Exception):
    """Custom exception that carries the data_result_key for error handling."""

    def __init__(self, message: str, data_result_key: str) -> None:
        super().__init__(message)
        self.data_result_key = data_result_key


# =============================================================================
# AsyncAction Definition
# =============================================================================


async def _fetch_handler(store: HasApiData, payload: FetchPayload) -> FetchResult:
    """Async handler that performs the 'fetch' (mocked).

    Succeeds if api_endpoint is "success.com", otherwise raises FetchError.
    """
    await asyncio.sleep(0.01)

    if payload.api_endpoint == "success.com":
        return FetchResult(
            key=payload.data_result_key,
            fetched_data={
                "message": "Data fetched successfully!",
                "source": payload.api_endpoint,
                "api_key_used": store.api_key,
            },
        )
    else:
        raise FetchError(
            f"Failed to fetch from {payload.api_endpoint}",
            data_result_key=payload.data_result_key,
        )


def _fetch_on_success(store: HasApiData, result: FetchResult) -> frozenset[str]:
    """Sync callback to mutate state on successful fetch."""
    store.data[result.key] = result.fetched_data
    return frozenset({f"data.{result.key}"})


def _fetch_on_error(store: HasApiData, error: Exception) -> frozenset[str]:
    """Sync callback to mutate state on fetch error."""
    if isinstance(error, FetchError):
        store.data[error.data_result_key] = {
            "error": True,
            "message": str(error),
        }
        return frozenset({f"data.{error.data_result_key}"})
    else:
        store.data["_error"] = {
            "error": True,
            "message": str(error),
            "type": type(error).__name__,
        }
        return frozenset({"data._error"})


fetch_data_action = AsyncAction[HasApiData, FetchPayload, FetchResult](
    handler=_fetch_handler,
    on_success=_fetch_on_success,
    on_error=_fetch_on_error,
)


# =============================================================================
# Store Subclass
# =============================================================================


class ApiDataStore(Store, HasApiData):
    """Concrete store that implements HasApiData protocol."""

    api_key: str
    data: dict[str, Any]

    fetch_data = fetch_data_action

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.data = {}
        super().__init__()


# =============================================================================
# Tests
# =============================================================================


class TestAsyncActionInstanceSuccess:
    """Tests for successful async action execution using instance pattern."""

    @pytest.mark.asyncio
    async def test_fetch_success_stores_data(self) -> None:
        """Successful fetch stores data correctly."""
        store = ApiDataStore(api_key="secret-key-123")

        payload = FetchPayload(api_endpoint="success.com", data_result_key="user_info")
        await store.fetch_data(payload)

        assert "user_info" in store.data
        assert store.data["user_info"]["message"] == "Data fetched successfully!"
        assert store.data["user_info"]["api_key_used"] == "secret-key-123"

    @pytest.mark.asyncio
    async def test_fetch_success_notifies_subscribers(self) -> None:
        """Successful fetch notifies subscribers with Delta."""
        store = ApiDataStore(api_key="secret-key-123")
        notifications: list[Delta] = []
        store.subscribe(lambda delta: notifications.append(delta))

        payload = FetchPayload(api_endpoint="success.com", data_result_key="user_info")
        await store.fetch_data(payload)

        assert len(notifications) == 1
        assert notifications[0].diff  # non-empty


class TestAsyncActionInstanceError:
    """Tests for error handling in async actions using instance pattern."""

    @pytest.mark.asyncio
    async def test_fetch_failure_stores_error(self) -> None:
        """Failed fetch stores error info via on_error callback."""
        store = ApiDataStore(api_key="secret-key-456")

        payload = FetchPayload(api_endpoint="fail.com", data_result_key="weather")
        await store.fetch_data(payload)

        assert "weather" in store.data
        assert store.data["weather"]["error"] is True
        assert "Failed to fetch" in store.data["weather"]["message"]

    @pytest.mark.asyncio
    async def test_fetch_failure_notifies_subscribers(self) -> None:
        """Failed fetch notifies subscribers with Delta."""
        store = ApiDataStore(api_key="secret-key-456")
        notifications: list[Delta] = []
        store.subscribe(lambda delta: notifications.append(delta))

        payload = FetchPayload(api_endpoint="fail.com", data_result_key="weather")
        await store.fetch_data(payload)

        assert len(notifications) == 1
        assert notifications[0].diff  # non-empty


class TestAsyncActionInstanceMultiple:
    """Tests for multiple async action invocations."""

    @pytest.mark.asyncio
    async def test_multiple_fetches_to_different_keys(self) -> None:
        """Multiple fetches store data under separate keys."""
        store = ApiDataStore(api_key="multi-key")
        notification_count = 0

        def on_change(_: Delta) -> None:
            nonlocal notification_count
            notification_count += 1

        store.subscribe(on_change)

        await store.fetch_data(FetchPayload("success.com", "data1"))
        await store.fetch_data(FetchPayload("error.com", "data2"))
        await store.fetch_data(FetchPayload("success.com", "data3"))

        assert "data1" in store.data and store.data["data1"].get("error") is None
        assert "data2" in store.data and store.data["data2"]["error"] is True
        assert "data3" in store.data and store.data["data3"].get("error") is None
        assert notification_count == 3


class TestAsyncActionErrorPropagation:
    """Tests for async action error handling edge cases."""

    @pytest.mark.asyncio
    async def test_error_propagates_without_on_error(self) -> None:
        """When no on_error provided, exception propagates to caller."""

        async def failing_handler(_store: HasApiData, _payload: str) -> str:
            raise ValueError("network failure")

        def on_success(store: HasApiData, result: str) -> frozenset[str]:
            store.data["result"] = result
            return frozenset({"data.result"})

        failing_action = AsyncAction[HasApiData, str, str](
            handler=failing_handler,
            on_success=on_success,
        )

        class FailingStore(Store, HasApiData):
            api_key: str
            data: dict[str, Any]
            do_fail = failing_action

            def __init__(self) -> None:
                self.api_key = ""
                self.data = {}
                super().__init__()

        store = FailingStore()

        with pytest.raises(ValueError, match="network failure"):
            await store.do_fail("test")

    @pytest.mark.asyncio
    async def test_async_action_returns_none(self) -> None:
        """Bound async action returns None, not the handler result."""
        store = ApiDataStore(api_key="test")

        result = await store.fetch_data(FetchPayload("success.com", "test"))

        assert result is None

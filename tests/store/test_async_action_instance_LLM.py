"""Tests for StoreUpdaterAsync pattern.

Tests the pattern of creating StoreUpdaterAsync instances and binding them
to an AgentApp, using Protocols for type safety.
"""

# pyright: reportPrivateUsage=false
# Tests need access to _store for verification.

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import pytest

from agent_lib.agent_app.AgentApp import AgentApp
from agent_lib.store.Store import Store
from agent_lib.store.StoreUpdaterAsync import StoreUpdaterAsync
from agent_lib.util.json_utils import JSONSchema


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
    """Payload for fetch_data updater."""

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
# StoreUpdaterAsync Definition
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


fetch_data_updater: StoreUpdaterAsync[Any, FetchPayload, FetchResult] = (
    StoreUpdaterAsync(
        name="fetch_data",
        description="Fetch data from an API endpoint.",
        payload_json_schema=JSONSchema({}),
        async_handler=_fetch_handler,
        on_success=_fetch_on_success,
        on_error=_fetch_on_error,
    )
)


# =============================================================================
# Store and App Subclass
# =============================================================================


class ApiDataStore(Store, HasApiData):
    """Concrete store that implements HasApiData protocol."""

    api_key: str
    data: dict[str, Any]

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.data = {}
        super().__init__()


class ApiDataApp(AgentApp[ApiDataStore]):
    """App with fetch_data capability bound."""

    def __init__(self, api_key: str) -> None:
        store = ApiDataStore(api_key)
        super().__init__(store)
        fetch_data_updater.bind(self)


# =============================================================================
# Tests
# =============================================================================


class TestStoreUpdaterAsyncSuccess:
    """Tests for successful async updater execution."""

    @pytest.mark.asyncio
    async def test_fetch_success_stores_data(self) -> None:
        """Successful fetch stores data correctly."""
        app = ApiDataApp(api_key="secret-key-123")
        store = app._store

        payload = FetchPayload(api_endpoint="success.com", data_result_key="user_info")
        await fetch_data_updater(payload)

        assert "user_info" in store.data
        assert store.data["user_info"]["message"] == "Data fetched successfully!"
        assert store.data["user_info"]["api_key_used"] == "secret-key-123"

    @pytest.mark.asyncio
    async def test_fetch_success_notifies_subscribers(self) -> None:
        """Successful fetch notifies subscribers with affects function."""
        app = ApiDataApp(api_key="secret-key-123")
        affected_paths: list[bool] = []
        app.subscribers.append(
            lambda affects: affected_paths.append(affects("data.user_info"))
        )

        payload = FetchPayload(api_endpoint="success.com", data_result_key="user_info")
        await fetch_data_updater(payload)

        assert len(affected_paths) == 1
        assert affected_paths[0] is True  # data.user_info was affected


class TestStoreUpdaterAsyncError:
    """Tests for error handling in async updaters."""

    @pytest.mark.asyncio
    async def test_fetch_failure_stores_error(self) -> None:
        """Failed fetch stores error info via on_error callback."""
        app = ApiDataApp(api_key="secret-key-456")
        store = app._store

        payload = FetchPayload(api_endpoint="fail.com", data_result_key="weather")
        await fetch_data_updater(payload)

        assert "weather" in store.data
        assert store.data["weather"]["error"] is True
        assert "Failed to fetch" in store.data["weather"]["message"]

    @pytest.mark.asyncio
    async def test_fetch_failure_notifies_subscribers(self) -> None:
        """Failed fetch notifies subscribers with affects function."""
        app = ApiDataApp(api_key="secret-key-456")
        affected_paths: list[bool] = []
        app.subscribers.append(
            lambda affects: affected_paths.append(affects("data.weather"))
        )

        payload = FetchPayload(api_endpoint="fail.com", data_result_key="weather")
        await fetch_data_updater(payload)

        assert len(affected_paths) == 1
        assert affected_paths[0] is True  # data.weather was affected


class TestStoreUpdaterAsyncMultiple:
    """Tests for multiple async updater invocations."""

    @pytest.mark.asyncio
    async def test_multiple_fetches_to_different_keys(self) -> None:
        """Multiple fetches store data under separate keys."""
        app = ApiDataApp(api_key="multi-key")
        store = app._store
        notification_count = 0

        def on_change(_: Callable[[str], bool]) -> None:
            nonlocal notification_count
            notification_count += 1

        app.subscribers.append(on_change)

        await fetch_data_updater(FetchPayload("success.com", "data1"))
        await fetch_data_updater(FetchPayload("error.com", "data2"))
        await fetch_data_updater(FetchPayload("success.com", "data3"))

        assert "data1" in store.data and store.data["data1"].get("error") is None
        assert "data2" in store.data and store.data["data2"]["error"] is True
        assert "data3" in store.data and store.data["data3"].get("error") is None
        assert notification_count == 3


class TestStoreUpdaterAsyncErrorPropagation:
    """Tests for async updater error handling edge cases."""

    @pytest.mark.asyncio
    async def test_error_propagates_without_on_error(self) -> None:
        """When no on_error provided, exception propagates to caller."""

        async def failing_handler(_store: HasApiData, _payload: str) -> str:
            raise ValueError("network failure")

        def on_success(store: HasApiData, result: str) -> frozenset[str]:
            store.data["result"] = result
            return frozenset({"data.result"})

        failing_updater: StoreUpdaterAsync[str, str, Any] = StoreUpdaterAsync(
            name="do_fail",
            description="Always fails.",
            payload_json_schema=JSONSchema({}),
            async_handler=failing_handler,
            on_success=on_success,
        )

        class FailingStore(Store, HasApiData):
            api_key: str
            data: dict[str, Any]

            def __init__(self) -> None:
                self.api_key = ""
                self.data = {}
                super().__init__()

        store = FailingStore()
        app: AgentApp[FailingStore] = AgentApp(store)
        failing_updater.bind(app)

        with pytest.raises(ValueError, match="network failure"):
            await failing_updater("test")

    @pytest.mark.asyncio
    async def test_async_updater_returns_none(self) -> None:
        """Bound async updater returns None, not the handler result."""
        _app = ApiDataApp(api_key="test")  # Creates and binds updater

        result = await fetch_data_updater(FetchPayload("success.com", "test"))

        assert result is None

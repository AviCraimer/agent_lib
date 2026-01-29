# A simple example of how to make a reusable StoreUpdaterAsync and attach it to an app.

# pyright: reportPrivateUsage=false
# Example code needs access to _store for testing/demonstration.

from __future__ import annotations


import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

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
    # Simulate async network delay
    await asyncio.sleep(0.05)

    if payload.api_endpoint == "success.com":
        return FetchResult(
            key=payload.data_result_key,
            fetched_data={
                "message": "Data fetched successfully!",
                "source": payload.api_endpoint,
                "api_key_used": store.api_key,
                "timestamp": "2024-01-15T10:30:00Z",
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
        # Unknown error type - store under generic key
        store.data["_error"] = {
            "error": True,
            "message": str(error),
            "type": type(error).__name__,
        }
        return frozenset({"data._error"})


# Create the StoreUpdaterAsync instance
fetch_data_updater: StoreUpdaterAsync[FetchPayload, FetchResult, Any] = StoreUpdaterAsync(
    name="fetch_data",
    description="Fetch data from an API endpoint.",
    payload_json_schema=JSONSchema(
        {
            "type": "object",
            "properties": {
                "api_endpoint": {"type": "string"},
                "data_result_key": {"type": "string"},
            },
            "required": ["api_endpoint", "data_result_key"],
        }
    ),
    async_handler=_fetch_handler,
    on_success=_fetch_on_success,
    on_error=_fetch_on_error,
)


# =============================================================================
# Store and App Subclasses
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
    """App that provides the fetch_data capability."""

    def __init__(self, api_key: str) -> None:
        store = ApiDataStore(api_key)
        super().__init__(store)
        # Bind the async updater
        fetch_data_updater.bind(self)


# =============================================================================
# Tests
# =============================================================================


async def test_fetch_success() -> None:
    """Test that fetch_data succeeds and stores data correctly."""
    print("\n=== Test: Fetch Success ===")

    app = ApiDataApp(api_key="secret-key-123")
    store = app._store

    # Track notifications
    affected_paths: list[bool] = []
    app.subscribers.append(lambda affects: affected_paths.append(affects("data.user_info")))

    # Dispatch the async updater
    payload = FetchPayload(api_endpoint="success.com", data_result_key="user_info")
    await fetch_data_updater(payload)

    # Verify state was updated
    assert "user_info" in store.data, "user_info should be in data"
    assert store.data["user_info"]["message"] == "Data fetched successfully!"
    assert store.data["user_info"]["api_key_used"] == "secret-key-123"

    # Verify we got a notification
    assert len(affected_paths) == 1, "Should have received one notification"
    print(f"  data.user_info affected: {affected_paths[0]}")

    print(f"  Store data: {store.data}")
    print("  Test passed!")


async def test_fetch_failure() -> None:
    """Test that fetch_data handles errors and stores error info."""
    print("\n=== Test: Fetch Failure ===")

    app = ApiDataApp(api_key="secret-key-456")
    store = app._store

    # Track notifications
    affected_paths: list[bool] = []
    app.subscribers.append(lambda affects: affected_paths.append(affects("data.weather")))

    # Dispatch the async updater with a failing endpoint
    payload = FetchPayload(api_endpoint="fail.com", data_result_key="weather")
    await fetch_data_updater(payload)

    # Verify error state was stored
    assert "weather" in store.data, "weather should be in data"
    assert store.data["weather"]["error"] is True
    assert "Failed to fetch" in store.data["weather"]["message"]

    # Verify we got a notification
    assert len(affected_paths) == 1, "Should have received one notification"
    print(f"  data.weather affected: {affected_paths[0]}")

    print(f"  Store data: {store.data}")
    print("  Test passed!")


async def test_multiple_fetches() -> None:
    """Test multiple fetches to different keys."""
    print("\n=== Test: Multiple Fetches ===")

    app = ApiDataApp(api_key="multi-key")
    store = app._store

    notification_count = 0

    def on_change(affects: Callable[[str], bool]) -> None:
        nonlocal notification_count
        notification_count += 1
        print(f"    Notification #{notification_count}: data affected = {affects('data')}")

    app.subscribers.append(on_change)

    # Successful fetch
    await fetch_data_updater(FetchPayload("success.com", "data1"))

    # Failed fetch
    await fetch_data_updater(FetchPayload("error.com", "data2"))

    # Another successful fetch
    await fetch_data_updater(FetchPayload("success.com", "data3"))

    # Verify all data is present
    assert "data1" in store.data and store.data["data1"].get("error") is None
    assert "data2" in store.data and store.data["data2"]["error"] is True
    assert "data3" in store.data and store.data["data3"].get("error") is None

    assert (
        notification_count == 3
    ), f"Expected 3 notifications, got {notification_count}"

    print(f"  Store data keys: {list(store.data.keys())}")
    print(f"  data1 (success): {store.data['data1']}")
    print(f"  data2 (error): {store.data['data2']}")
    print(f"  data3 (success): {store.data['data3']}")
    print("  Test passed!")


async def main() -> None:
    """Run all tests."""
    print("=" * 70)
    print("StoreUpdaterAsync Example - Running Tests")
    print("=" * 70)

    await test_fetch_success()
    await test_fetch_failure()
    await test_multiple_fetches()

    print("\n" + "=" * 70)
    print("All tests passed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol
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


# Create the AsyncAction instance
fetch_data_action = AsyncAction[HasApiData, FetchPayload, FetchResult](
    handler=_fetch_handler,
    on_success=_fetch_on_success,
    on_error=_fetch_on_error,
)


# =============================================================================
# Store Subclass (inherits from Store and satisfies HasApiData protocol)
# =============================================================================


class ApiDataStore(Store, HasApiData):
    """Concrete store that implements HasApiData protocol."""

    api_key: str
    data: dict[str, Any]

    # Attach the async action as a class attribute
    fetch_data = fetch_data_action

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.data = {}
        super().__init__()


# =============================================================================
# Tests
# =============================================================================


async def test_fetch_success() -> None:
    """Test that fetch_data succeeds and stores data correctly."""
    print("\n=== Test: Fetch Success ===")

    store = ApiDataStore(api_key="secret-key-123")

    # Track notifications
    notifications: list[Delta] = []
    store.subscribe(lambda delta: notifications.append(delta))

    # Dispatch the async action
    payload = FetchPayload(api_endpoint="success.com", data_result_key="user_info")
    await store.fetch_data(payload)

    # Verify state was updated
    assert "user_info" in store.data, "user_info should be in data"
    assert store.data["user_info"]["message"] == "Data fetched successfully!"
    assert store.data["user_info"]["api_key_used"] == "secret-key-123"

    # Verify we got a notification
    assert len(notifications) == 1, "Should have received one notification"
    print(f"  Notification diff: {notifications[0].diff}")

    print(f"  Store data: {store.data}")
    print("  ✓ Test passed!")


async def test_fetch_failure() -> None:
    """Test that fetch_data handles errors and stores error info."""
    print("\n=== Test: Fetch Failure ===")

    store = ApiDataStore(api_key="secret-key-456")

    # Track notifications
    notifications: list[Delta] = []
    store.subscribe(lambda delta: notifications.append(delta))

    # Dispatch the async action with a failing endpoint
    payload = FetchPayload(api_endpoint="fail.com", data_result_key="weather")
    await store.fetch_data(payload)

    # Verify error state was stored
    assert "weather" in store.data, "weather should be in data"
    assert store.data["weather"]["error"] is True
    assert "Failed to fetch" in store.data["weather"]["message"]

    # Verify we got a notification
    assert len(notifications) == 1, "Should have received one notification"
    print(f"  Notification diff: {notifications[0].diff}")

    print(f"  Store data: {store.data}")
    print("  ✓ Test passed!")


async def test_multiple_fetches() -> None:
    """Test multiple fetches to different keys."""
    print("\n=== Test: Multiple Fetches ===")

    store = ApiDataStore(api_key="multi-key")

    notification_count = 0

    def on_change(delta: Delta) -> None:
        nonlocal notification_count
        notification_count += 1
        print(f"    Notification #{notification_count}: {delta.diff}")

    store.subscribe(on_change)

    # Successful fetch
    await store.fetch_data(FetchPayload("success.com", "data1"))

    # Failed fetch
    await store.fetch_data(FetchPayload("error.com", "data2"))

    # Another successful fetch
    await store.fetch_data(FetchPayload("success.com", "data3"))

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
    print("  ✓ Test passed!")


async def test_unsubscribe() -> None:
    """Test that unsubscribe works correctly."""
    print("\n=== Test: Unsubscribe ===")

    store = ApiDataStore(api_key="unsub-key")

    notification_count = 0

    def on_change(_: Delta) -> None:
        nonlocal notification_count
        notification_count += 1

    unsubscribe = store.subscribe(on_change)

    # First fetch - should notify
    await store.fetch_data(FetchPayload("success.com", "before_unsub"))
    assert notification_count == 1

    # Unsubscribe
    unsubscribe()

    # Second fetch - should NOT notify
    await store.fetch_data(FetchPayload("success.com", "after_unsub"))
    assert (
        notification_count == 1
    ), "Should not have received notification after unsubscribe"

    # Verify both fetches still updated the store
    assert "before_unsub" in store.data
    assert "after_unsub" in store.data

    print(f"  Notifications received: {notification_count} (expected 1)")
    print("  ✓ Test passed!")


async def main() -> None:
    """Run all tests."""
    print("=" * 70)
    print("AsyncAction Store Example - Running Tests")
    print("=" * 70)

    await test_fetch_success()
    await test_fetch_failure()
    await test_multiple_fetches()
    await test_unsubscribe()

    print("\n" + "=" * 70)
    print("All tests passed! ✓")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

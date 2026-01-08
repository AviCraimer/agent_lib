"""Example demonstrating protocol-based async actions.

Async actions are defined separately from stores and work against protocols,
enabling better modularity and testability.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from agent_lib.store.AsyncAction import AsyncAction
from agent_lib.store.Store import Store


# Define a protocol for what the async action needs
class HasDataFields(Protocol):
    data: dict[str, Any] | None
    error: str | None
    loading: bool


# Define the async action against the protocol (not a concrete store)
class FetchData(AsyncAction[HasDataFields, str, dict[str, Any]]):
    """Fetch data from a URL and store the result."""

    async def handler(self, store: HasDataFields, payload: str) -> dict[str, Any]:
        """Simulate async fetch - in real code this would use aiohttp/httpx."""
        store.loading = True
        await asyncio.sleep(0.1)  # Simulate network delay
        # Simulate response
        return {"url": payload, "status": "ok", "data": [1, 2, 3]}

    def on_success(self, store: HasDataFields, result: dict[str, Any]) -> frozenset[str]:
        """Store the fetched data."""
        store.data = result
        store.loading = False
        return frozenset({"data", "loading"})

    def on_error(self, store: HasDataFields, error: Exception) -> frozenset[str]:
        """Handle fetch errors."""
        store.error = str(error)
        store.loading = False
        return frozenset({"error", "loading"})


# Store implements the protocol and uses the action
class MyStore(Store):
    data: dict[str, Any] | None
    error: str | None
    loading: bool

    def __init__(self) -> None:
        super().__init__()
        self.data = None
        self.error = None
        self.loading = False

    # Assign the async action as a class attribute
    fetch_data = FetchData()


async def main() -> None:
    store = MyStore()

    print(f"Initial state: data={store.data}, loading={store.loading}")

    # Call the async action
    await store.fetch_data("https://api.example.com/data")

    print(f"After fetch: data={store.data}, loading={store.loading}")


if __name__ == "__main__":
    asyncio.run(main())
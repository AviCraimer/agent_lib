"""Test that type checker catches protocol mismatches.

This file should produce type errors because BadStore doesn't implement HasDataFields.
"""

from __future__ import annotations

from typing import Any, Protocol

from agent_lib.store.AsyncAction import AsyncAction
from agent_lib.store.Store import Store


# Define a protocol for what the async action needs
class HasDataFields(Protocol):
    data: dict[str, Any] | None
    error: str | None
    loading: bool


# Define the async action against the protocol
class FetchData(AsyncAction[HasDataFields, str, dict[str, Any]]):
    async def handler(self, store: HasDataFields, payload: str) -> dict[str, Any]:
        store.loading = True
        return {"result": "ok"}

    def on_success(self, store: HasDataFields, result: dict[str, Any]) -> frozenset[str]:
        store.data = result
        store.loading = False
        return frozenset({"data", "loading"})


# This store does NOT implement the protocol - should cause type error
class BadStore(Store):
    name: str  # Wrong fields!

    def __init__(self) -> None:
        super().__init__()
        self.name = "bad"

    # Attaching FetchData here should be a type error
    # because BadStore doesn't have data, error, loading fields
    fetch_data = FetchData()


# This store DOES implement the protocol - should be fine
class GoodStore(Store):
    data: dict[str, Any] | None
    error: str | None
    loading: bool

    def __init__(self) -> None:
        super().__init__()
        self.data = None
        self.error = None
        self.loading = False

    fetch_data = FetchData()


async def test_bad_store() -> None:
    bad = BadStore()
    # This should ideally be a type error - BadStore doesn't implement HasDataFields
    await bad.fetch_data("test")


async def test_good_store() -> None:
    good = GoodStore()
    # This should be fine
    await good.fetch_data("test")
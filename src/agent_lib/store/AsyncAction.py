from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Self, overload

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class AsyncAction[S, PL, R]:
    """Base class for async actions. Subclass and implement handler, on_success, on_error.

    S: Protocol or type the store must implement (enables interface segregation)
    PL: The payload type (input to async handler)
    R: The result type (returned by async handler, passed to on_success)

    Async actions are defined separately from stores and work against protocols,
    enabling better modularity and testability.

    Usage:
        # Define a protocol for what the action needs
        class HasDataField(Protocol):
            data: dict
            error: str | None

        # Define the action against the protocol
        class FetchData(AsyncAction[HasDataField, str, dict]):
            async def handler(self, store: HasDataField, url: str) -> dict:
                async with aiohttp.get(url) as resp:
                    return await resp.json()

            def on_success(self, store: HasDataField, data: dict) -> frozenset[str]:
                store.data = data
                return frozenset({"data"})

            def on_error(self, store: HasDataField, error: Exception) -> frozenset[str]:
                store.error = str(error)
                return frozenset({"error"})

        # Store implements the protocol and uses the action
        class MyStore(Store):
            data: dict
            error: str | None

            fetch_data = FetchData()  # Assign instance as class attribute
    """

    _name: str

    def __set_name__(self, owner: type, name: str) -> None:
        """Capture the attribute name when assigned to a class."""
        self._name = name

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> Self: ...

    @overload
    def __get__(self, obj: Store, objtype: type | None = None) -> BoundAsyncAction[S, PL, R]: ...

    def __get__(self, obj: Store | None, objtype: type | None = None) -> BoundAsyncAction[S, PL, R] | Self:
        """Descriptor protocol: return bound action when accessed on instance."""
        if obj is None:
            return self
        return BoundAsyncAction(self, obj)

    @abstractmethod
    async def handler(self, store: S, payload: PL) -> R:
        """Perform async work (read-only). Override in subclass.

        Args:
            store: The store instance (typed as protocol S)
            payload: The input payload

        Returns:
            Result to be passed to on_success
        """
        ...

    @abstractmethod
    def on_success(self, store: S, result: R) -> frozenset[str]:
        """Mutate state after successful async work. Override in subclass.

        Args:
            store: The store instance (typed as protocol S)
            result: The result from handler

        Returns:
            frozenset of paths that were mutated (for diffing)
        """
        ...

    def on_error(self, store: S, error: Exception) -> frozenset[str]:
        """Handle errors from async work. Override in subclass if needed.

        Default implementation returns empty frozenset (no-op).

        Args:
            store: The store instance (typed as protocol S)
            error: The exception that was raised

        Returns:
            frozenset of paths that were mutated (for diffing)
        """
        return frozenset()


class BoundAsyncAction[S, PL, R]:
    """A bound async action ready to be called with just a payload.

    Created by AsyncAction.__get__ when accessed on a store instance.
    """

    __slots__ = ("action", "store")

    def __init__(self, action: AsyncAction[S, PL, R], store: Store) -> None:
        self.action = action
        self.store = store

    async def __call__(self, payload: PL) -> None:
        """Execute the async action.

        1. Calls handler to perform async work
        2. On success: snapshots state, calls on_success, diffs, notifies
        3. On error: calls on_error if defined, otherwise re-raises
        """
        await self.store.run_async_action(self.action, payload)
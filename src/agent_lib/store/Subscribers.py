"""Subscription management for Store."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

from deepdiff import Delta

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class Subscribers:
    """Manages store subscription callbacks.

    Provides list-like interface for backward compatibility while
    encapsulating subscription management logic.
    """

    _store: Store
    _callbacks: list[Callable[[Delta], None]]

    def __init__(self, store: Store) -> None:
        self._store = store
        self._callbacks = []

    def append(self, callback: Callable[[Delta], None]) -> None:
        """Add a subscription callback."""
        self._callbacks.append(callback)

    def remove(self, callback: Callable[[Delta], None]) -> None:
        """Remove a subscription callback."""
        self._callbacks.remove(callback)

    def notify(self, delta: Delta) -> None:
        """Notify all subscribers of state changes.

        Args:
            delta: The Delta object containing all changes from the action
        """
        if not delta.diff:  # empty = no changes
            return
        for callback in self._callbacks:
            callback(delta)

    def __iter__(self) -> Iterator[Callable[[Delta], None]]:
        """Allow iteration over callbacks."""
        return iter(self._callbacks)

    def __len__(self) -> int:
        """Return number of subscribers."""
        return len(self._callbacks)

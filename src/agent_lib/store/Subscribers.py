"""Subscription management for Store."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

from deepdiff import Delta, parse_path

if TYPE_CHECKING:
    from agent_lib.store.Store import Store

# Callback receives an `affects` function to check if a path was changed
type SubscriberCallback = Callable[[Callable[[str], bool]], None]


def _normalize_delta_path(delta_path: str) -> str:
    """Convert DeepDiff path like root['data']['name'] to dot notation 'data.name'."""
    parts = parse_path(delta_path)
    return ".".join(str(p) for p in parts)


def _make_affects(delta: Delta) -> Callable[[str], bool]:
    """Create an `affects` helper from a Delta.

    The returned function checks if a given path was affected by the change.

    Args:
        delta: The Delta object from DeepDiff

    Returns:
        Function that takes a path string and returns True if that path was changed
    """
    # Pre-compute normalized paths for all changes
    normalized_paths: set[str] = set()
    if delta.diff:
        for change_type in delta.diff.values():
            if isinstance(change_type, dict):
                for delta_path in change_type:
                    normalized_paths.add(_normalize_delta_path(delta_path))

    def affects(path: str) -> bool:
        """Check if a path was affected by this change.

        Args:
            path: Dot-notation path like "_state.current_text" or partial like "current_text"

        Returns:
            True if any change in the delta affects this path
        """
        if not normalized_paths:
            return False

        for normalized in normalized_paths:
            # Match if path is anywhere in the normalized path (partial match)
            if path in normalized:
                return True
        return False

    return affects


class Subscribers:
    """Manages store subscription callbacks.

    Subscribers receive an `affects(path)` function to check if specific
    paths were changed, abstracting away the Delta internals.
    """

    _store: Store
    _callbacks: list[SubscriberCallback]

    def __init__(self, store: Store) -> None:
        self._store = store
        self._callbacks = []

    def append(self, callback: SubscriberCallback) -> None:
        """Add a subscription callback."""
        self._callbacks.append(callback)

    def remove(self, callback: SubscriberCallback) -> None:
        """Remove a subscription callback."""
        self._callbacks.remove(callback)

    def notify(self, delta: Delta) -> None:
        """Notify all subscribers of state changes.

        Args:
            delta: The Delta object containing all changes from the action
        """
        if not delta.diff:  # empty = no changes
            return

        affects = _make_affects(delta)
        for callback in self._callbacks:
            callback(affects)

    def __iter__(self) -> Iterator[SubscriberCallback]:
        """Allow iteration over callbacks."""
        return iter(self._callbacks)

    def __len__(self) -> int:
        """Return number of subscribers."""
        return len(self._callbacks)

from __future__ import annotations

from collections.abc import Coroutine
from typing import Any, Callable, ClassVar

# Type alias for bound actions (after binding to a Store instance)
type BoundAction[T] = Callable[[T], None] | Callable[[T], Coroutine[Any, Any, None]]


class Action[T, S]:
    """An action that can be defined as a class attribute on a Store subclass.

    T: The payload type
    S: The state type

    Actions mutate state and return a frozenset of paths indicating where they mutated.
    This "scope" tells the system which subtrees to diff for change detection.
    """

    class scope:
        """Helper constants for action return values (avoid magic strings)."""

        no_op: ClassVar[frozenset[str]] = frozenset()
        """Return this when action made no changes - skips diff and notifications."""

        full_diff: ClassVar[frozenset[str]] = frozenset({"."})
        """Return this when scope is unknown - diffs entire state tree."""

    def __init__(self, handler: Callable[[S, T], frozenset[str]]):
        self.handler = handler

    def __call__(self, payload: T) -> frozenset[str]:
        # This is only called if accessed on the class directly (not via instance)
        raise RuntimeError(
            "Action must be accessed via a Store instance, not the class. "
            "Use store.action_name() instead of StoreClass.action_name()"
        )

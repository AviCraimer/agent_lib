from __future__ import annotations

from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Callable, ClassVar

if TYPE_CHECKING:
    from agent_lib.store.Store import Store

# Type alias for bound actions (after binding to a Store instance)
type BoundAction[T] = Callable[[T], None] | Callable[[T], Coroutine[Any, Any, None]]


class Action[S: Store, PL]:
    """An action that can be defined as a class attribute on a Store subclass.

    S: The store type (S will be a sub-class of Store)
    PL: The payload type

    Actions mutate state and return a frozenset of paths indicating where they mutated.
    This "scope" tells the system which subtrees to diff for change detection.
    """

    class scope:
        """Helper constants for action return values (avoid magic strings)."""

        no_op: ClassVar[frozenset[str]] = frozenset()
        """Return this when action made no changes - skips diff and notifications."""

        full_diff: ClassVar[frozenset[str]] = frozenset({"."})
        """Return this when scope is unknown - diffs entire state tree."""

    def __init__(self, handler: Callable[[S, PL], frozenset[str]]):
        self.handler = handler

    def __call__(self, payload: PL) -> frozenset[str]:
        # This is only called if accessed on the class directly (not via instance)
        raise RuntimeError(
            "You've tried to call an unbound action. The action is callable after being bound to a store instance."
            "i.e., use store.my_bound_action(payload) instead of my_unbound_action(payload)."
        )

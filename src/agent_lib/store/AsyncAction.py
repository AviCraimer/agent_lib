from __future__ import annotations

from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class AsyncAction[S: Store, PL, R]:
    """An async action that can be defined as a class attribute on a Store subclass.

    S: The store type (S will be a sub-class of Store)
    PL: The payload type (input to async handler)
    R: The result type (returned by async handler, passed to on_success)

    Async actions perform read-only async work and return a result.
    The result is passed to on_success which performs the actual state mutation.
    This separation ensures proper snapshot/diff/notify flow for state changes.
    """

    handler: Callable[[S, PL], Coroutine[Any, Any, R]]
    on_success: Callable[[S, R], frozenset[str]]
    on_error: Callable[[S, Exception], frozenset[str]] | None

    def __init__(
        self,
        handler: Callable[[S, PL], Coroutine[Any, Any, R]],
        on_success: Callable[[S, R], frozenset[str]],
        on_error: Callable[[S, Exception], frozenset[str]] | None = None,
    ):
        self.handler = handler
        self.on_success = on_success
        self.on_error = on_error

    def __call__(self, payload: PL) -> Coroutine[Any, Any, None]:
        # This is only called if accessed on the class directly (not via instance)
        raise RuntimeError(
            "AsyncAction must be accessed via a Store instance, not the class. "
            "Use `await store.action_name()` instead of `await StoreClass.action_name()`"
        )

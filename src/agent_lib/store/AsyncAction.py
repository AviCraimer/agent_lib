from __future__ import annotations

from collections.abc import Coroutine
from typing import Any, Callable


class AsyncAction[PL, St, R]:
    """An async action that can be defined as a class attribute on a Store subclass.

    PL: The payload type (input to async handler)
    St: The state type
    R: The result type (returned by async handler, passed to on_success)

    Async actions perform read-only async work and return a result.
    The result is passed to on_success which performs the actual state mutation.
    This separation ensures proper snapshot/diff/notify flow for state changes.
    """

    handler: Callable[[St, PL], Coroutine[Any, Any, R]]
    on_success: Callable[[St, R], frozenset[str]]
    on_error: Callable[[St, Exception], frozenset[str]] | None

    def __init__(
        self,
        handler: Callable[[St, PL], Coroutine[Any, Any, R]],
        on_success: Callable[[St, R], frozenset[str]],
        on_error: Callable[[St, Exception], frozenset[str]] | None = None,
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

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any


class AsyncAction[S, PL, R]:
    """An async action that can be defined as a class attribute on a Store subclass.

    S: This argument will get the instance of the store passed to it. For reusable async actions, the type S will generally be filled in with a Protocol that describes the fields that are necessary. Any Store subclasses that include async actions must inherit from all the S-protocols used in those actions.
    PL: The payload type (input to async handler)
    R: The result type (returned by async handler, passed to on_success)

    The handler performs read-only async work and returns a result or raises an Exception.
    If a result is returned, it is passed to on_success which performs the actual state mutation.
    If an exception is raised, it is passed to on_error which may also mutate the state.

    Note that both on_success and on_error should be synchronous functions.

    This separation ensures proper snapshot/diff/notify flow for state changes.

    Scope Format:
        on_success and on_error return a frozenset of dot-notation paths indicating which parts of the store were modified. This enables efficient diffing.
        Examples:
        - frozenset({'data.user_info'}) - nested path
        - frozenset({'config'}) - root attribute
        - frozenset({'.'}) - triggers full diff (use sparingly)

    Example Usage:
    fetch_data_action = AsyncAction[HasApiDataProtocol, FetchDataPayload, FetchResult](
    handler=  fetch_handler,
    on_success= fetch_on_success,
    on_error= fetch_on_error,
    )
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

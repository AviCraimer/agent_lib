from __future__ import annotations

from typing import Callable


class Action[T, S]:
    """An action that can be defined as a class attribute on a Store subclass.

    T: The payload type
    S: The state type
    """

    def __init__(self, handler: Callable[[S, T], S]):
        self.handler = handler

    def __call__(self, payload: T) -> S:
        # This is only called if accessed on the class directly (not via instance)
        raise RuntimeError(
            "Action must be accessed via a Store instance, not the class. "
            "Use store.action_name() instead of StoreClass.action_name()"
        )

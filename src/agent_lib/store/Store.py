from __future__ import annotations

from typing import Callable

from agent_lib.component.ContextComponent import ContextComponent


class Store[S]:
    _state: S

    def __init__(self, initial_state: S):
        self._state = initial_state

    def get(self) -> S:
        return self._state

    def set(self, new_state: S) -> None:
        self._state = new_state

    def connect[P](
        self,
        component: ContextComponent[P],
        selector: Callable[[S], P],
    ) -> ContextComponent[None]:
        def new_render(_: None, __: str) -> str:
            props = selector(self._state)
            return component.render_unwrapped(props)

        return ContextComponent[None](
            new_render, component.delimitor, None, props_bound=True
        )

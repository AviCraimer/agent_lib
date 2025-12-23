from __future__ import annotations

from typing import Callable, overload

from agent_lib.component.ContextComponent import ContextComponent


class Action[T, S]:
    """An action that can be connected to a store to mutate state.

    T: The payload type
    S: The state type
    """

    def __init__(self, handler: Callable[[S, T], S]):
        self.handler = handler


class Store[S]:
    _state: S

    def __init__(self, initial_state: S):
        self._state = initial_state

    def get(self) -> S:
        return self._state

    def set(self, new_state: S) -> None:
        self._state = new_state

    @overload
    def connect[P](
        self,
        target: ContextComponent[P],
        selector: Callable[[S], P],
    ) -> ContextComponent[None]: ...

    @overload
    def connect[T](
        self,
        target: Action[T, S],
    ) -> Callable[[T], S]: ...

    def connect[P, T](
        self,
        target: ContextComponent[P] | Action[T, S],
        selector: Callable[[S], P] | None = None,
    ) -> ContextComponent[None] | Callable[[T], S]:
        if isinstance(target, ContextComponent):
            if selector is None:
                raise ValueError("selector is required when connecting a component")
            return self._connect_component(target, selector)
        elif isinstance(target, Action):
            return self._connect_action(target)
        else:
            raise TypeError(f"Cannot connect {type(target)}")

    def _connect_component[P](
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

    def _connect_action[T](
        self,
        action: Action[T, S],
    ) -> Callable[[T], S]:
        def bound(payload: T) -> S:
            return action.handler(self._state, payload)

        return bound

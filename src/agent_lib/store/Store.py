from __future__ import annotations

from typing import Any, Callable, overload

from agent_lib.component.ContextComponent import ContextComponent
from agent_lib.store.Action import Action


class Store[S]:
    _state: S
    _actions: dict[str, Callable[..., frozenset[str]]]

    @staticmethod
    def action[T, St](handler: Callable[[St, T], frozenset[str]]) -> Action[T, St]:
        """Decorator to define an action on a Store subclass."""
        return Action(handler)

    def __init__(self, initial_state: S):
        self._state = initial_state
        self._actions = {}
        self._bind_actions()

    def _bind_actions(self) -> None:
        """Find all Action class attributes and bind them to this instance."""
        for name in dir(type(self)):
            if name.startswith("_"):
                continue
            attr = getattr(type(self), name)
            if isinstance(attr, Action):
                # Create bound action - captures self and attr
                def make_bound(action: Action[Any, S]) -> Callable[..., frozenset[str]]:
                    def bound(payload: Any) -> frozenset[str]:
                        return action.handler(self.get(), payload)

                    return bound

                bound_action = make_bound(attr)
                self._actions[name] = bound_action
                setattr(self, name, bound_action)

    def get_actions(self, *names: str) -> dict[str, Callable[..., frozenset[str]]]:
        """Get bound actions by name. If no names provided, returns all actions."""
        if not names:
            return self._actions.copy()
        return {n: self._actions[n] for n in names if n in self._actions}

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
    ) -> Callable[[T], frozenset[str]]: ...

    def connect[P, T](
        self,
        target: ContextComponent[P] | Action[T, S],
        selector: Callable[[S], P] | None = None,
    ) -> ContextComponent[None] | Callable[[T], frozenset[str]]:
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
    ) -> Callable[[T], frozenset[str]]:
        def bound(payload: T) -> frozenset[str]:
            return action.handler(self.get(), payload)

        return bound

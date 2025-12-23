from __future__ import annotations

from typing import Any, Callable, overload

from deepdiff import DeepDiff, Delta
from glom import T, glom

from agent_lib.component.ContextComponent import ContextComponent
from agent_lib.store.Action import Action
from agent_lib.store.snapshot import snapshot


class Store[S]:
    _state: S
    _actions: dict[str, Callable[..., None]]

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
                def make_bound(action: Action[Any, S]) -> Callable[..., None]:
                    def bound(payload: Any) -> None:
                        delta = self._process_action(action.handler, payload)
                        self._notify_subscribers(delta)

                    return bound

                bound_action = make_bound(attr)
                self._actions[name] = bound_action
                setattr(self, name, bound_action)

    def _process_action(
        self, handler: Callable[[S, Any], frozenset[str]], payload: Any
    ) -> Delta:
        """Run action handler and return Delta representing all changes.

        Args:
            handler: The action handler function (state, payload) -> scope
            payload: The payload to pass to the handler

        Returns:
            Delta object containing all changes, or empty Delta for no-op
        """
        state_snapshot = snapshot(self._state)
        scope = handler(self._state, payload)

        if not scope:  # no-op
            return Delta({})

        combined = Delta({})
        for scope_path in scope:
            # Use T for root access when path is "."
            spec = T if scope_path == "." else scope_path
            old_subtree = glom(state_snapshot, spec)
            new_subtree = glom(self._state, spec)
            diff = DeepDiff(old_subtree, new_subtree)
            combined = combined + Delta(diff)

        return combined

    def _notify_subscribers(self, delta: Delta) -> None:
        """Notify subscribers of state changes. Implemented in Section 5."""
        pass  # Stub - will be implemented with subscription system

    def get_actions(self, *names: str) -> dict[str, Callable[..., None]]:
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
    ) -> Callable[[T], None]: ...

    def connect[P, T](
        self,
        target: ContextComponent[P] | Action[T, S],
        selector: Callable[[S], P] | None = None,
    ) -> ContextComponent[None] | Callable[[T], None]:
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
    ) -> Callable[[T], None]:
        def bound(payload: T) -> None:
            delta = self._process_action(action.handler, payload)
            self._notify_subscribers(delta)

        return bound

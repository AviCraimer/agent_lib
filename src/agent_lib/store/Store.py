from __future__ import annotations

from collections.abc import Coroutine, Callable
from typing import Any, Self, overload

from deepdiff import DeepDiff, Delta

from agent_lib.context.CxtComponent import CtxComponent
from agent_lib.context.Props import NoProps, Props
from agent_lib.store.Action import Action
from agent_lib.store.AsyncAction import AsyncAction
from agent_lib.store.snapshot import snapshot


class Store:
    _actions: dict[str, Callable[..., None]]
    _subscribers: list[Callable[[Delta], None]]

    @classmethod
    def action[PL](
        cls: type[Self], handler: Callable[[Self, PL], frozenset[str]]
    ) -> Action[Self, PL]:
        """Decorator to define an action on a Store subclass."""
        return Action(handler)

    @classmethod
    def async_action[PL, R](
        cls: type[Self],
        on_success: Callable[[Self, R], frozenset[str]],
        on_error: Callable[[Self, Exception], frozenset[str]] | None = None,
    ) -> Callable[
        [Callable[[Self, PL], Coroutine[Any, Any, R]]], AsyncAction[Self, PL, R]
    ]:
        """Decorator factory to define an async action on a Store subclass.

        Args:
            on_success: Handler called with async result to mutate state
            on_error: Optional handler called with exception to mutate state

        Returns:
            Decorator that wraps async function into AsyncAction
        """

        def decorator(
            handler: Callable[[Self, PL], Coroutine[Any, Any, R]],
        ) -> AsyncAction[Self, PL, R]:
            return AsyncAction(handler, on_success, on_error)

        return decorator

    def __init__(self) -> None:
        self._actions = {}
        self._subscribers = []
        self._bind_actions()
        self._bind_async_actions()

    def _bind_actions(self) -> None:
        """Find all Action class attributes and bind them to this instance."""
        for name in dir(type(self)):
            if name.startswith("_"):
                continue
            attr = getattr(type(self), name)
            if isinstance(attr, Action):
                # Create bound action - captures self and attr
                def make_bound(action: Action[Self, Any]) -> Callable[..., None]:
                    def bound(payload: Any) -> None:
                        delta = self._process_action(action.handler, payload)
                        self._notify_subscribers(delta)

                    return bound

                bound_action = make_bound(attr)
                self._actions[name] = bound_action
                setattr(self, name, bound_action)

    def _bind_async_actions(self) -> None:
        """Find all AsyncAction class attributes and bind them to this instance."""
        for name in dir(type(self)):
            if name.startswith("_"):
                continue
            attr = getattr(type(self), name)
            if isinstance(attr, AsyncAction):

                def make_bound(
                    async_action: AsyncAction[Self, Any, Any],
                ) -> Callable[..., Coroutine[Any, Any, None]]:
                    async def bound(payload: Any) -> None:
                        await self._run_async_action(async_action, payload)

                    return bound

                bound_action = make_bound(attr)
                setattr(self, name, bound_action)

    async def _run_async_action(
        self, async_action: AsyncAction[Self, Any, Any], payload: Any
    ) -> None:
        """Execute async action and process result through on_success/on_error.

        Args:
            async_action: The AsyncAction containing handler and hooks
            payload: The payload to pass to the async handler
        """
        try:
            # Async work (read-only, no snapshot taken here)
            result = await async_action.handler(self, payload)
            # Sync mutation with full snapshot → mutate → diff → notify flow
            delta = self._process_action(async_action.on_success, result)
            self._notify_subscribers(delta)
        except Exception as e:
            if async_action.on_error:
                delta = self._process_action(async_action.on_error, e)
                self._notify_subscribers(delta)
            else:
                raise

    def _process_action(
        self, handler: Callable[[Self, Any], frozenset[str]], payload: Any
    ) -> Delta:
        """Run action handler and return Delta representing all changes.

        Args:
            handler: The action handler function (state, payload) -> scope
            payload: The payload to pass to the handler

        Returns:
            Delta object containing all changes, or empty Delta for no-op
        """
        state_snapshot = snapshot(self)
        scope = handler(self, payload)

        if not scope:  # no-op
            return Delta({})

        # "." means full diff, otherwise restrict to specified paths
        include = None if "." in scope else list(scope)
        diff = DeepDiff(state_snapshot, self, include_paths=include)
        return Delta(diff)

    def _notify_subscribers(self, delta: Delta) -> None:
        """Notify all subscribers of state changes.

        Args:
            delta: The Delta object containing all changes from the action
        """
        if not delta.diff:  # empty = no changes
            return
        for subscriber in self._subscribers:
            subscriber(delta)

    def subscribe(self, callback: Callable[[Delta], None]) -> Callable[[], None]:
        """Subscribe to state changes.

        Args:
            callback: Function to call with Delta when state changes

        Returns:
            Unsubscribe function - call it to remove the subscription
        """
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def get_actions(self, *names: str) -> dict[str, Callable[..., None]]:
        """Get bound actions by name. If no names provided, returns all actions."""
        if not names:
            return self._actions.copy()
        return {n: self._actions[n] for n in names if n in self._actions}

    @overload
    def connect[P: Props](
        self,
        target: CtxComponent[P],
        selector: Callable[[Self], P],
    ) -> CtxComponent[NoProps]: ...

    @overload
    def connect[T](
        self,
        target: Action[Self, T],
    ) -> Callable[[T], None]: ...

    def connect[P: Props, T](
        self,
        target: CtxComponent[P] | Action[Self, T],
        selector: Callable[[Self], P] | None = None,
    ) -> CtxComponent[NoProps] | Callable[[T], None]:
        if isinstance(target, CtxComponent):
            if selector is None:
                raise ValueError("selector is required when connecting a component")
            return self._connect_component(target, selector)
        elif isinstance(target, Action):
            return self._connect_action(target)
        else:
            raise TypeError(f"Cannot connect {type(target)}")

    def _connect_component[P: Props](
        self,
        component: CtxComponent[P],
        selector: Callable[[Self], P],
    ) -> CtxComponent[NoProps]:
        def new_render(_: NoProps) -> str:
            props = selector(self)
            return component.render(props)

        return CtxComponent[NoProps](new_render, NoProps)

    def _connect_action[T](
        self,
        action: Action[Self, T],
    ) -> Callable[[T], None]:
        def bound(payload: T) -> None:
            delta = self._process_action(action.handler, payload)
            self._notify_subscribers(delta)

        return bound

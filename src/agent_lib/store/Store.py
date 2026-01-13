from __future__ import annotations

from collections.abc import Coroutine, Callable
from typing import Any, Self, cast, overload

from deepdiff import DeepDiff, Delta, parse_path

from agent_lib.agent.AgentState import AgentState
from agent_lib.context.CxtComponent import CtxComponent
from agent_lib.context.Props import NoProps, Props
from agent_lib.store.Action import Action
from agent_lib.store.AsyncAction import AsyncAction
from agent_lib.store.snapshot import snapshot


class Store:
    _actions: dict[str, Callable[..., None]]
    _subscribers: list[Callable[[Delta], None]]

    @staticmethod
    def action[S: Store, PL](
        handler: Callable[[S, PL], frozenset[str]],
    ) -> Action[S, PL]:
        """Decorator to define a synchronous action method on a Store subclass. This facilitates defining sync action handlers as regular class methods in place when defining a store subclass. Of couse, the action class instances may also be defined separately added as store properties. This is useful if you have actions that are reused across different store classes.

        Note: For async actions it is best to define them as AsyncAction instances separately and add them as store class properties.
        Usage:
            class MyStore(Store):
                @Store.action
                def set_value(self, value: str) -> frozenset[str]:
                    self.value = value
                    return frozenset({"value"})

        How typing works:
            The type parameter `S` is inferred from the decorated method's `self` parameter. When `self` is not explicitly annotated, Python's type checker infers it as `Self` (the enclosing class), so `S` correctly resolves to the Store subclass (e.g., `MyStore`).

        Failure mode:
            If you explicitly annotate `self` with a superclass type, the type checker will use that instead. This compiles but loses subclass type information. However, this is rarely an issue in practice since developers almost never explicitly annotate `self`.
        """
        return Action(handler)

    def __init__(self) -> None:
        """When calling this as __super__.init() in subclasses, ensure it is after class properties (actions, agent_state, etc) have been assigned."""
        self._actions = {}
        self._subscribers = []
        self._bind_actions()
        self._bind_async_actions()
        self.validate_agent_state()

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
        self, async_action: AsyncAction[Any, Any, Any], payload: Any
    ) -> None:
        """Execute async action and process result through on_success/on_error.
        Note: For type safety, the Store subclass should inherit from the protocols of any async actions it possesses as class properties.

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
        self, handler: Callable[[Any, Any], frozenset[str]], payload: Any
    ) -> Delta:
        """Run action handler and return Delta representing all changes.

        For type safety, the action must either take the Store subclass as its
        first argument type, or use a protocol that is inherited by the store subclass.

        Args:
            handler: The action handler function (state, payload) -> scope
            payload: The payload to pass to the handler

        Returns:
            Delta object containing all changes, or empty Delta for no-op

        Scope format:
            Actions return a frozenset of dot-notation paths indicating which
            parts of the store were modified, e.g., frozenset({'data.user_info'}).
            Use '.' as a scope element to trigger a full diff of the entire store.
        """
        state_snapshot = snapshot(self)
        scope = handler(self, payload)

        if not scope:  # no-op
            return Delta({})

        # "." means full diff, otherwise filter to specified scope paths
        if "." in scope:
            diff = DeepDiff(state_snapshot, self)
        else:
            diff = DeepDiff(
                state_snapshot,
                self,
                include_obj_callback=self._make_scope_filter(
                    scope
                ),  # This ensures DeepDiff only diffs the indicated scope.
            )
        return Delta(diff)

    @staticmethod
    def _make_scope_filter(
        scopes: frozenset[str],
    ) -> Callable[[object, str], bool]:
        """Create a DeepDiff include_obj_callback that filters to given scopes.

        Args:
            scopes: Set of dot-notation paths, e.g., {'data.user_info', 'config'}

        Returns:
            Callback function for DeepDiff's include_obj_callback parameter
        """

        def callback(_obj: object, path: str) -> bool:
            # Normalize DeepDiff path (e.g., root.data['key']) to dot notation
            normalized = ".".join(cast(list[str], parse_path(path)))
            if not normalized:  # root - always traverse
                return True
            for scope in scopes:
                # Include if path is within scope OR scope is within path (for traversal)
                if normalized.startswith(scope) or scope.startswith(normalized):
                    return True
            return False

        return callback

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

    def validate_agent_state(self) -> None:
        """Validate that agent_state dict keys match agent_name attributes."""
        agent_state: dict[str, AgentState] | None = getattr(self, "agent_state", None)
        if agent_state is None:
            return

        if not isinstance(agent_state, dict):
            raise TypeError("agent_state must be a dict[str, AgentState]")

        for key, state in agent_state.items():
            if not isinstance(state, AgentState):
                raise TypeError(
                    f"agent_state['{key}'] must be an AgentState, "
                    f"got {type(state).__name__}"
                )
            if key != state.agent_name:
                raise ValueError(
                    f"agent_state key '{key}' doesn't match agent_name '{state.agent_name}'"
                )

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
        else:
            return self._connect_action(target)

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

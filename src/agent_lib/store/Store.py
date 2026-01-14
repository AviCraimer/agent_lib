from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Self, TypedDict, overload

from deepdiff import DeepDiff, Delta, parse_path

from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps, Props
from agent_lib.store.Action import Action
from agent_lib.store.Agents import Agents
from agent_lib.store.AsyncAction import AsyncAction
from agent_lib.store.Fanouts import Fanouts
from agent_lib.store.snapshot import snapshot
from agent_lib.store.State import State
from agent_lib.store.Subscribers import Subscribers


class UpdateShouldActPayload(TypedDict):
    """Payload for the update_should_act action."""

    agent_name: str
    should_act: bool


class Store:
    _actions: dict[str, Callable[..., None]]
    _subscribers: Subscribers
    _fanouts: Fanouts
    _agents: Agents
    _state: State

    @staticmethod
    def action[S: Store, PL](
        handler: Callable[[S, PL], frozenset[str]],
    ) -> Action[S, PL]:
        """Decorator to define a synchronous action method on a Store subclass.

        This facilitates defining sync action handlers as regular class methods in place when defining a store subclass. Of course, the action class instances may also be defined separately and added as store properties. This is useful if you have actions that are reused across different store classes.

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
        """Initialize the store with composed components.

        When calling this as super().__init__() in subclasses, ensure it is after class properties (actions, _state, etc) have been assigned.
        """
        self._actions = {}
        if not hasattr(self, "_state"):
            self._state = State()
        self._subscribers = Subscribers(self)
        self._agents = Agents(self)
        self._agents.validate()
        self._fanouts = Fanouts(self)
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
                        self._subscribers.notify(delta)

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
            # Sync mutation with full snapshot -> mutate -> diff -> notify flow
            delta = self._process_action(async_action.on_success, result)
            self._subscribers.notify(delta)
        except Exception as e:
            if async_action.on_error:
                delta = self._process_action(async_action.on_error, e)
                self._subscribers.notify(delta)
            else:
                raise

    def _process_action(
        self, handler: Callable[[Any, Any], frozenset[str]], payload: Any
    ) -> Delta:
        """Run action handler and return Delta representing all changes.

        For type safety, the action must either take the Store subclass as its first argument type, or use a protocol that is inherited by the store subclass.

        Args:
            handler: The action handler function (state, payload) -> scope
            payload: The payload to pass to the handler

        Returns:
            Delta object containing all changes, or empty Delta for no-op

        Scope format:
            Actions return a frozenset of dot-notation paths indicating which parts of the store were modified, e.g., frozenset({'data.user_info'}). Use '.' as a scope element to trigger a full diff of the entire store.
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
                include_obj_callback=self._make_scope_filter(scope),
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
            # parse_path returns strings for keys and ints for list indices
            normalized = ".".join(str(p) for p in parse_path(path))
            if not normalized:  # root - always traverse
                return True
            for scope in scopes:
                # Include if path is within scope OR scope is within path (for traversal)
                if normalized.startswith(scope) or scope.startswith(normalized):
                    return True
            return False

        return callback

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
            self._subscribers.notify(delta)

        return bound

    @action
    def update_should_act(
        self, payload: UpdateShouldActPayload
    ) -> frozenset[str]:
        """Update an agent's should_act flag.

        This is a core action used by AgentRuntime to control agent execution.
        Agents can use this (via a tool) to signal completion or to activate other agents.

        Args:
            payload: Contains agent_name and should_act boolean

        Returns:
            Scope indicating agent_state was modified
        """
        agent_name = payload["agent_name"]
        self._state.agent_state[agent_name].should_act = payload["should_act"]
        return frozenset({"_state.agent_state"})

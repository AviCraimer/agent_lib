"""Store - manages application state.

Store holds the state tree and provides component connection. State mutations are handled
through StoreUpdaters (which are Tools), keeping the Store focused on state management
while AgentApp handles the agent lifecycle and notification flow.
"""

from __future__ import annotations

from collections.abc import Callable
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps, Props
from agent_lib.store.snapshot import snapshot
from agent_lib.store.state.AgentState import validate_agent_state
from agent_lib.store.state.State import State
from agent_lib.util.diff_utils import make_scope_filter
from deepdiff import DeepDiff, Delta


class Store[StateT: State = State]:
    """Manages application state.

    Store is the single source of truth for application state. It provides:
    - State storage via `_state` attribute
    - Read-only state access via `state` property (returns snapshot)
    - A notify callback property which is provided by the AgentApp to update store subscribers when state is set.
    - set_state method to set state, and provide an optional diff scope to speed up mutation comparison.
    - Component connection via `connect()` for binding components to state

    State mutations are handled by StoreUpdaters, which are Tools that:
    1. Receive a state snapshot for mutation access
    2. Return a diff scope

    This separation keeps Store simple and focused on state, while AgentApp handles agent lifecycle, tool management, and subscriber notifications.
    """

    _state: StateT
    notify: Callable[[Delta], None] = lambda d: None  # This will be set externally

    def __init__(self, state: StateT) -> None:
        """Initialize the store with composed components.

        When calling this as super().__init__() in subclasses, ensure it is after
        class properties (_state, etc) have been assigned.
        """

        self._state = state
        validate_agent_state(self._state.agent_state)

    @property
    def state(self) -> StateT:
        """Return a snapshot (deep copy) of the current state.

        This provides read-only access to state. Modifications to the returned
        object do not affect the actual state.
        """
        return snapshot(self._state)

    def set_state(self, state: StateT, scope: frozenset[str]):
        prev_state = self._state
        self._state = state
        delta = self.get_delta(prev_state, scope)
        self.notify(delta)

    def get_delta(self, prev_state: StateT, scope: frozenset[str]) -> Delta:

        if not scope:  # no-op
            return Delta()
        # "." means full diff, otherwise filter to specified scope paths
        if "." in scope:
            diff = DeepDiff(prev_state, self._state)
        else:
            diff = DeepDiff(
                prev_state,
                self._state,
                include_obj_callback=make_scope_filter(scope),
            )
        return Delta(diff)

    def connect[P: Props](
        self,
        component: CtxComponent[P],
        map_to_props: Callable[[StateT], P],
    ) -> CtxComponent[NoProps]:
        """Connect a component to the store, binding it to derived state.

        Creates a new component that automatically derives its props from the
        store's current state when rendered.

        Args:
            component: The component to connect
            map_to_props: Function that extracts props from the store

        Returns:
            A new component that takes NoProps and derives its state from the store

        Example:
            UserInfo = store.connect(
                UserInfoComponent,
                lambda s: UserInfoProps(name=s._state.user.name)
            )
            # Later, UserInfo renders with current state automatically
            context = UserInfo.render(NoProps())
        """

        def new_render(_: NoProps) -> str:
            props = map_to_props(self._state)
            return component.render(props)

        return CtxComponent[NoProps](new_render, NoProps)

"""Store - manages application state.

Store holds the state tree and provides component connection. State mutations are handled
through StoreUpdaters (which are Tools), keeping the Store focused on state management
while AgentApp handles the agent lifecycle and notification flow.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Self

from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps, Props
from agent_lib.store.snapshot import snapshot
from agent_lib.store.state.AgentState import validate_agent_state
from agent_lib.store.state.State import State


class Store[StateT: State = State]:
    """Manages application state.

    Store is the single source of truth for application state. It provides:
    - State storage via `_state` attribute
    - Read-only state access via `state` property (returns snapshot)
    - Component connection via `connect()` for binding components to state

    State mutations are handled by StoreUpdaters, which are Tools that:
    1. Receive the Store for mutation access
    2. Handle snapshot/diff/notify flow automatically
    3. Notify AgentApp subscribers of changes

    This separation keeps Store simple and focused on state, while AgentApp
    handles agent lifecycle, tool management, and subscriber notifications.
    """

    _state: StateT

    def __init__(self) -> None:
        """Initialize the store with composed components.

        When calling this as super().__init__() in subclasses, ensure it is after
        class properties (_state, etc) have been assigned.
        """
        if not hasattr(self, "_state"):
            self._state = State()  # type: ignore[assignment]
        validate_agent_state(self._state.agent_state)
        self._fanouts = Fanouts(self)

    @property
    def state(self) -> StateT:
        """Return a snapshot (deep copy) of the current state.

        This provides read-only access to state. Modifications to the returned
        object do not affect the actual state.
        """
        return snapshot(self._state)

    def connect[P: Props](
        self,
        component: CtxComponent[P],
        selector: Callable[[Self], P],
    ) -> CtxComponent[NoProps]:
        """Connect a component to the store, binding it to derived state.

        Creates a new component that automatically derives its props from the
        store's current state when rendered.

        Args:
            component: The component to connect
            selector: Function that extracts props from the store

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
            props = selector(self)
            return component.render(props)

        return CtxComponent[NoProps](new_render, NoProps)

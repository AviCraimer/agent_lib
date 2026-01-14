"""Agent state management for Store."""

# pyright: reportPrivateUsage=false
# This module is an internal Store component that needs access to Store internals.

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_lib.agent.AgentState import AgentState

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class Agents:
    """Manages agent state and validation."""

    _store: Store

    def __init__(self, store: Store) -> None:
        self._store = store

    def validate(self) -> None:
        """Validate that agent_state dict keys match agent_name attributes.

        Raises:
            TypeError: If agent_state is not a dict or contains non-AgentState values
            ValueError: If any key doesn't match its AgentState.agent_name
        """
        agent_state = self._store._state.agent_state
        if not agent_state:
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

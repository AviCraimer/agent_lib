"""Core action for updating agent should_act flags.

This action is used by AgentRuntime to control agent execution.
Agents can use this (via a tool) to signal completion or to activate other agents.

This is automatically included in the base Store class.
"""

# pyright: reportPrivateUsage=false
# Actions need access to Store internals (_state) to modify state.

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from agent_lib.store.Action import Action

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class UpdateShouldActPayload(TypedDict):
    """Payload for the update_should_act action."""

    agent_name: str
    should_act: bool


def _update_should_act_handler(
    store: Store, payload: UpdateShouldActPayload
) -> frozenset[str]:
    """Update an agent's should_act flag.

    Args:
        store: The Store instance
        payload: Contains agent_name and should_act boolean

    Returns:
        Scope indicating agent_state was modified
    """
    agent_name = payload["agent_name"]
    store._state.agent_state[agent_name].should_act = payload["should_act"]
    return frozenset({"_state.agent_state"})


update_should_act: Action[Store, UpdateShouldActPayload] = Action(
    _update_should_act_handler
)

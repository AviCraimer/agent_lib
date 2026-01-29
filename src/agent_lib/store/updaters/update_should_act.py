"""Core updater for updating agent should_act flags.

This updater is used by AgentApp to control agent execution.
Agents can use this (via a tool) to signal completion or to activate other agents.
"""

# pyright: reportPrivateUsage=false
# StoreUpdaters need access to Store internals (_state) to modify state.

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from agent_lib.store.StoreUpdater import StoreUpdater
from agent_lib.util.json_utils import JSONSchema

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class UpdateShouldActPayload(TypedDict):
    """Payload for the update_should_act updater."""

    agent_name: str
    should_act: bool


# TOD): Update to use decorator
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
    store.state.agent_state[agent_name].should_act = payload["should_act"]
    return frozenset({"_state.agent_state"})


update_should_act: StoreUpdater[UpdateShouldActPayload, Store] = StoreUpdater(
    name="update_should_act",
    description="Update an agent's should_act flag. Use to signal completion or activate other agents.",
    payload_json_schema=JSONSchema(
        {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string"},
                "should_act": {"type": "boolean"},
            },
            "required": ["agent_name", "should_act"],
        }
    ),
    updater=_update_should_act_handler,
)

"""Core updater for updating agent should_act flags.

This updater is used by AgentApp to control agent execution.
Agents can use this (via a tool) to signal completion or to activate other agents.
"""

# pyright: reportPrivateUsage=false
# StoreUpdaters need access to Store internals (_state) to modify state.

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from agent_lib.store.StoreUpdater import StoreUpdater, store_updater
from agent_lib.util.json_utils import JSONSchema

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class UpdateShouldActPayload(TypedDict):
    """Payload for the update_should_act updater."""

    agent_name: str
    should_act: bool


update_should_act_schema = JSONSchema(
    {
        "type": "object",
        "properties": {
            "agent_name": {"type": "string"},
            "should_act": {"type": "boolean"},
        },
        "required": ["agent_name", "should_act"],
    }
)


@store_updater(schema=update_should_act_schema)
def update_should_act(store: Store, payload: UpdateShouldActPayload) -> frozenset[str]:
    """Update an agent's `should_act` flag. When an agent's should_act flag is on it will act every turn until its flag is switched off."""
    agent_name = payload["agent_name"]
    store.state.agent_state[agent_name].should_act = payload["should_act"]
    return frozenset({"_state.agent_state"})

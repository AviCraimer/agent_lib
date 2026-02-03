"""Pre-defined StoreUpdater for recording message history.

This updater is broadly useful for chat-based agents but not universal to all applications.
Import and bind to your AgentApp if needed.

Usage:
    from agent_lib.store.updaters.record_history import record_history, RecordHistoryPayload

    # In your AgentApp subclass:
    record_history.bind(self)
    record_history(RecordHistoryPayload(agent_name="agent", messages=[...]))
"""

# pyright: reportPrivateUsage=false
# StoreUpdaters need access to Store internals (_state) to modify state.

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from agent_lib.store.StoreUpdater import store_updater
from agent_lib.util.json_utils import JSONSchema

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class RecordHistoryPayload(TypedDict):
    """Payload for the record_history updater."""

    agent_name: str
    messages: list[dict[str, str]]


record_history_schema = JSONSchema(
    {
        "type": "object",
        "properties": {
            "agent_name": {"type": "string"},
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
            },
        },
        "required": ["agent_name", "messages"],
    }
)


@store_updater(schema=record_history_schema)
def record_history(store: Store, payload: RecordHistoryPayload) -> frozenset[str]:
    """Append messages to an agent's history.

    Args:
        store: The Store instance
        payload: Contains agent_name and messages to append

    Returns:
        Scope indicating agent_state was modified
    """
    agent_name = payload["agent_name"]
    messages = payload["messages"]
    store.state.agent_state[agent_name].history.extend(messages)
    return frozenset({"_state.agent_state"})


# TODO: Can we add the agent_name to this diff string?

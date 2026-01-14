"""Pre-defined action for recording message history.

This action is broadly useful for chat-based agents but not universal to all applications.
Import and add to your Store subclass if needed.

Usage:
    from agent_lib.store.actions.record_history import record_history, RecordHistoryPayload

    class MyStore(Store):
        # Add as a class attribute
        record_history = record_history
"""

# pyright: reportPrivateUsage=false
# Actions need access to Store internals (_state) to modify state.

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from agent_lib.store.Action import Action

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class RecordHistoryPayload(TypedDict):
    """Payload for the record_history action."""

    agent_name: str
    messages: list[dict[str, str]]


def _record_history_handler(store: Store, payload: RecordHistoryPayload) -> frozenset[str]:
    """Append messages to an agent's history.

    Args:
        store: The Store instance
        payload: Contains agent_name and messages to append

    Returns:
        Scope indicating agent_state was modified
    """
    agent_name = payload["agent_name"]
    messages = payload["messages"]
    store._state.agent_state[agent_name].history.extend(messages)
    return frozenset({"_state.agent_state"})


record_history: Action[Store, RecordHistoryPayload] = Action(_record_history_handler)

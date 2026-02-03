"""Used by AgentApp to update an the state of a given agent.

This updater is used by AgentApp to control agent execution.
This would not generally be used directly as a tool by an LLM agent as it does not have any guardrails. As such it does not provide a JSON schema for the payload.
"""

from __future__ import annotations

from agent_lib.store.StoreUpdater import store_updater
from agent_lib.store.state.AgentState import AgentState
from agent_lib.store.state.State import State
from agent_lib.util.diff_utils import join_diff_path


@store_updater
def update_agent_state[S: State](state: S, payload: AgentState | str) -> frozenset[str]:
    """
    state: S is the state subsclass used by the AgentApp.
    payload: is either an agent state which is used for setting or updating and agent's state. If a string is passed, this is treated as an agent name to remove from the state.
    """

    diff_path: str

    if isinstance(payload, str):
        del state.agent_state[payload]
        diff_path = "agent_state"
    else:
        name = payload.agent_name
        state.agent_state[name] = payload

        diff_path = join_diff_path(["agent_state", name])

    return frozenset({diff_path})

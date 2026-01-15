"""Base class for agent state within a multi-agent application.

AgentState is not a Store itself - it's a state container meant to be composed
into a larger Store. Each agent sees its own AgentState plus shared state,
and communicates with other agents through the shared state.

Example:
    class AppStore(Store):
        agent_state: dict[str, AgentState]
        shared: SharedState

        def __init__(self) -> None:
            self.agent_state = {
                "planner": AgentState(agent_name="planner"),
                "executor": AgentState(agent_name="executor"),
            }
            self.shared = SharedState()
            super().__init__() # This validates agent_state

"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_lib.tool.ToolMetadata import ToolMetadata


@dataclass
class AgentState:
    """Base class for agent-specific state.

    Attributes:
        agent_name: Unique identifier for this agent. Must match the key
            in the parent store's agent_state dict.
        active: Whether this agent is currently active/enabled.
        should_act: Signal that the agent should take its next action.
            Typically set by orchestration logic or other agents via
            actions on the shared state.
        history: Message history for this agent. Uses Sequence so developers can narrow with a TypedDict if needed.
        tools: Tool metadata for tools granted to this agent. Used by system prompts to describe available tools.
    """

    agent_name: str
    active: bool = field(default=False)
    should_act: bool = field(default=False)
    history: list[dict[str, str]] = field(default_factory=list)
    tools: list[ToolMetadata] = field(default_factory=list)


def validate_agent_state(agent_state: dict[str, AgentState] | None) -> None:
    """Validate that agent_state dict keys match agent_name attributes.

    Raises:
        TypeError: If agent_state is not a dict or contains non-AgentState values
        ValueError: If any key doesn't match its AgentState.agent_name
    """
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

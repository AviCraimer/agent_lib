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

from agent_lib.agent.ToolMetadata import ToolMetadata


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

"""Agent - runtime agent with granted tools.

Agent instances live outside the Store (in AgentRuntime) to maintain security boundaries.
Agents hold a reference to their AgentState (which lives in Store._state.agent_state)
but the Store cannot access Agent instances.
"""

from __future__ import annotations

from typing import Any

from agent_lib.agent.AgentState import AgentState
from agent_lib.agent.Tool import Tool


class Agent:
    """Runtime agent with granted tools.

    Agents are the behavioral component - they hold tools (capabilities) and can invoke them.
    The agent's state data lives in the Store, but the Agent instance itself is managed
    by AgentRuntime, which is separate from the Store.

    This separation ensures that actions (which receive the Store) cannot access
    Agent instances directly, providing a security boundary.
    """

    name: str
    state: AgentState
    tools: dict[str, Tool[Any, Any]]

    def __init__(self, name: str, state: AgentState) -> None:
        """Create an agent with a reference to its state.

        Args:
            name: Unique identifier for this agent (should match state.agent_name)
            state: Reference to AgentState in Store._state.agent_state
        """
        if name != state.agent_name:
            raise ValueError(f"Agent name '{name}' doesn't match state.agent_name '{state.agent_name}'")
        self.name = name
        self.state = state
        self.tools = {}

    def grant_tool(self, tool: Tool[Any, Any]) -> None:
        """Grant a tool to this agent.

        Args:
            tool: The tool to grant
        """
        self.tools[tool.name] = tool

    def revoke_tool(self, name: str) -> None:
        """Revoke a tool from this agent.

        Args:
            name: Name of the tool to revoke

        Raises:
            KeyError: If the tool is not granted to this agent
        """
        if name not in self.tools:
            raise KeyError(f"Tool '{name}' is not granted to agent '{self.name}'")
        del self.tools[name]

    def has_tool(self, name: str) -> bool:
        """Check if the agent has a specific tool."""
        return name in self.tools

    def invoke(self, tool_name: str, payload: Any) -> Any:
        """Invoke a tool by name with the given payload.

        Args:
            tool_name: Name of the tool to invoke
            payload: Payload to pass to the tool

        Returns:
            The result from the tool

        Raises:
            KeyError: If the tool is not granted to this agent
        """
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' is not granted to agent '{self.name}'")
        return self.tools[tool_name](payload)

    def list_tools(self) -> list[str]:
        """List the names of all tools granted to this agent."""
        return list(self.tools.keys())

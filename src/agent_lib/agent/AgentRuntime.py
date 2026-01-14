"""AgentRuntime - manages agent lifecycle, separate from Store.

AgentRuntime holds Agent instances outside of Store, maintaining the security boundary
that prevents actions from accessing Agent behavior directly.
"""

# pyright: reportPrivateUsage=false
# AgentRuntime needs access to Store internals (_state, _actions) to manage agent lifecycle.

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from agent_lib.agent.Agent import Agent
from agent_lib.agent.AgentState import AgentState
from agent_lib.agent.Tool import Tool

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class AgentRuntime:
    """Manages agent lifecycle, separate from Store.

    AgentRuntime maintains the security boundary between agent data (in Store._state.agent_state)
    and agent behavior (Agent instances held here). Actions receive the Store but cannot
    access AgentRuntime or Agent instances.

    Agent state is accessed through the runtime, not through Agent instances directly.
    This keeps the Store as the single source of truth for all state.

    Usage:
        store = MyStore()
        runtime = AgentRuntime(store)

        # Create an agent - adds state to Store and creates Agent instance
        planner = runtime.create_agent("planner")

        # Access agent state through the runtime
        state = runtime.get_agent_state("planner")

        # Grant tools to the agent
        planner.grant_tool(some_tool)

        # Wrap a Store action as a tool
        set_value_tool = runtime.action_to_tool("set_value")
        planner.grant_tool(set_value_tool)
    """

    _store: Store
    _agents: dict[str, Agent]

    def __init__(self, store: Store) -> None:
        """Create an AgentRuntime managing agents for the given Store.

        Args:
            store: The Store whose agent_state this runtime manages
        """
        self._store = store
        self._agents = {}

    def create_agent(
        self,
        name: str,
        state_class: type[AgentState] = AgentState,
        **state_kwargs: Any,
    ) -> Agent:
        """Create a new agent, adding its state to the Store.

        Args:
            name: Unique identifier for the agent
            state_class: AgentState subclass to use (default: AgentState)
            **state_kwargs: Additional kwargs passed to state_class constructor

        Returns:
            The created Agent instance

        Raises:
            ValueError: If an agent with this name already exists
        """
        if name in self._agents:
            raise ValueError(f"Agent '{name}' already exists")

        # Create state and add to Store
        state = state_class(agent_name=name, **state_kwargs)
        self._store._state.agent_state[name] = state

        # Create Agent instance (held here, not in Store)
        agent = Agent(name=name)
        self._agents[name] = agent

        return agent

    def get_agent(self, name: str) -> Agent | None:
        """Get an agent by name, or None if not found."""
        return self._agents.get(name)

    def get_agent_state(self, name: str) -> AgentState | None:
        """Get an agent's state from the Store, or None if not found."""
        return self._store._state.agent_state.get(name)

    def remove_agent(self, name: str) -> None:
        """Remove an agent, deleting its state from the Store.

        Args:
            name: Name of the agent to remove

        Raises:
            KeyError: If the agent doesn't exist
        """
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' does not exist")

        del self._agents[name]
        del self._store._state.agent_state[name]

    def list_agents(self) -> list[str]:
        """List the names of all agents."""
        return list(self._agents.keys())

    def action_to_tool(
        self,
        action_name: str,
        tool_name: str | None = None,
        description: str = "",
        json_schema: str = "",
    ) -> Tool[Any, None]:
        """Wrap a Store action as a Tool for agents.

        The returned Tool invokes the Store action when called, but the agent
        never sees the Store directly - only the payload goes in and the action runs.

        Args:
            action_name: Name of the action on the Store to wrap
            tool_name: Name for the tool (defaults to action_name)
            description: Human-readable description of what the tool does
            json_schema: JSON schema string describing the payload format. If the payload is a Pydandic model this can be auto-generated with MyPayload.model_json_schema() although for LLMs it may help to add additional descriptions to the schema manually.

        Returns:
            A Tool that wraps the Store action

        Raises:
            KeyError: If the action doesn't exist on the Store
        """
        if action_name not in self._store._actions:
            raise KeyError(f"Action '{action_name}' does not exist on Store")

        bound_action = self._store._actions[action_name]
        name = tool_name or action_name

        def handler(payload: Any) -> None:
            bound_action(payload)

        return Tool(
            name=name, description=description, json_schema=json_schema, handler=handler
        )

    def make_tool[P, R](
        self,
        name: str,
        description: str,
        json_schema: str,
        handler: Callable[[P], R],
    ) -> Tool[P, R]:
        """Create a custom tool (convenience method).

        Args:
            name: Tool name
            description: Human-readable description
            json_schema: JSON schema string describing the payload format
            handler: Function to call when tool is invoked

        Returns:
            The created Tool
        """
        return Tool(
            name=name, description=description, json_schema=json_schema, handler=handler
        )

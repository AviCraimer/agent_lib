"""AgentRuntime - manages agent lifecycle, separate from Store.

AgentRuntime holds Agent instances outside of Store, maintaining the security boundary
that prevents actions from accessing Agent behavior directly. It also holds tool handlers
and executes tool calls returned by agents.
"""

# pyright: reportPrivateUsage=false
# AgentRuntime needs access to Store internals (_state, _actions) to manage agent lifecycle.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from agent_lib.agent.Agent import Agent
from agent_lib.store.state.AgentState import AgentState
from agent_lib.agent.LLMClient import LLMClient
from agent_lib.tool.Tool import Tool
from agent_lib.context.components.ChatMessages import ChatMessages, ChatMessagesProps
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps
from agent_lib.util.json_utils import JSONSchema

if TYPE_CHECKING:
    from agent_lib.store.Store import Store


class AgentRuntime:
    """Manages agent lifecycle, separate from Store.

    AgentRuntime maintains the security boundary between agent data (in Store._state.agent_state)
    and agent behavior (Agent instances held here). Actions receive the Store but cannot
    access AgentRuntime or Agent instances.

    Tool handlers are stored in the runtime while tool metadata lives in agent state.
    When an agent returns tool calls from step(), the runtime executes them using the stored handlers.

    Usage:
        store = MyStore()
        runtime = AgentRuntime(store)

        # Create an agent - adds state to Store and creates Agent instance
        planner = runtime.create_agent("planner", llm_client, system_prompt)

        # Grant tools to the agent (metadata goes to state, handler stays in runtime)
        runtime.grant_tool("planner", some_tool)

        # Wrap a Store action as a tool and grant it
        set_value_tool = runtime.action_to_tool("set_value")
        runtime.grant_tool("planner", set_value_tool)

        # Run the agent loop
        runtime.run()
    """

    _store: Store
    _agents: dict[str, Agent]
    _tools: dict[str, dict[str, Tool[Any, Any]]]  # agent_name -> tool_name -> Tool

    def __init__(self, store: Store) -> None:
        """Create an AgentRuntime managing agents for the given Store.

        Args:
            store: The Store whose agent_state this runtime manages
        """
        self._store = store
        self._agents = {}
        self._tools = {}

    def create_agent(
        self,
        name: str,
        llm_client: LLMClient,
        system_prompt: CtxComponent[NoProps],
        messages: CtxComponent[NoProps] | None = None,
        state_class: type[AgentState] = AgentState,
        should_act_access: frozenset[str] | Literal["all"] = frozenset(),
        **state_kwargs: Any,
    ) -> Agent:
        """Create a new agent, adding its state to the Store.

        Args:
            name: Unique identifier for the agent
            llm_client: The LLM client for the agent to use
            system_prompt: The system prompt component for building context
            messages: Optional custom messages component. If not provided, uses ChatMessages connected to the agent's history in state.
            state_class: AgentState subclass to use (default: AgentState)
            should_act_access: Controls which agents this agent can update should_act for.
                "all" allows updating any agent, a frozenset restricts to named agents.
                Default is empty frozenset (no should_act tool granted).
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

        # Initialize tool storage for this agent
        self._tools[name] = {}

        # Create messages component - use provided or default to ChatMessages
        if messages is None:
            messages = self._store.connect(
                ChatMessages,
                lambda s, n=name: ChatMessagesProps(
                    history=s._state.agent_state[n].history
                ),
            )

        # Create context (connected to store, renders dynamically)
        context = LLMContext(system_prompt=system_prompt, messages=messages)

        # Create state selector for read-only access
        def get_state(agent_name: str = name) -> AgentState:
            return self._store._state.agent_state[agent_name]

        # Create Agent instance (held here, not in Store)
        agent = Agent(
            name=name, llm_client=llm_client, context=context, get_state=get_state
        )
        self._agents[name] = agent

        # Grant should_act tool if access is specified (empty frozenset is falsy, "all" is truthy)
        if should_act_access:
            tool = self.make_should_act_tool(should_act_access)
            self.grant_tool(name, tool)

        return agent

    def grant_tool(self, agent_name: str, tool: Tool[Any, Any]) -> None:
        """Grant a tool to an agent.

        Adds tool metadata to agent's state and stores the handler in the runtime.

        Args:
            agent_name: Name of the agent to grant the tool to
            tool: The tool to grant

        Raises:
            KeyError: If the agent doesn't exist
        """
        if agent_name not in self._agents:
            raise KeyError(f"Agent '{agent_name}' does not exist")

        # Add metadata to agent state
        metadata = tool.to_metadata()
        state = self._store._state.agent_state[agent_name]
        state.tools.append(metadata)

        # Store handler in runtime
        self._tools[agent_name][tool.name] = tool

    def revoke_tool(self, agent_name: str, tool_name: str) -> None:
        """Revoke a tool from an agent.

        Removes tool metadata from agent's state and removes the handler from the runtime.

        Args:
            agent_name: Name of the agent to revoke the tool from
            tool_name: Name of the tool to revoke

        Raises:
            KeyError: If the agent or tool doesn't exist
        """
        if agent_name not in self._agents:
            raise KeyError(f"Agent '{agent_name}' does not exist")

        if tool_name not in self._tools[agent_name]:
            raise KeyError(f"Tool '{tool_name}' is not granted to agent '{agent_name}'")

        # Remove metadata from agent state
        state = self._store._state.agent_state[agent_name]
        state.tools = [t for t in state.tools if t.name != tool_name]

        # Remove handler from runtime
        del self._tools[agent_name][tool_name]

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
        del self._tools[name]
        del self._store._state.agent_state[name]

    def list_agents(self) -> list[str]:
        """List the names of all agents."""
        return list(self._agents.keys())

    def action_to_tool(
        self,
        action_name: str,
        tool_name: str | None = None,
        description: str = "",
        json_schema: JSONSchema = JSONSchema({}),
    ) -> Tool[Any, None]:
        """Wrap a Store action as a Tool for agents.

        The returned Tool invokes the Store action when called, but the agent
        never sees the Store directly - only the payload goes in and the action runs.

        Args:
            action_name: Name of the action on the Store to wrap
            tool_name: Name for the tool (defaults to action_name)
            description: Human-readable description of what the tool does
            json_schema: JSON schema describing the payload format. If the payload is a Pydantic model this can be auto-generated with MyPayload.model_json_schema() although for LLMs it may help to add additional descriptions to the schema manually.

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

    def make_should_act_tool(
        self,
        allowed_agents: frozenset[str] | Literal["all"],
    ) -> Tool[dict[str, Any], None]:
        """Create a should_act tool with constrained agent access.

        Args:
            allowed_agents: Either "all" to allow updating any agent,
                or a frozenset of agent names that can be updated.

        Returns:
            A Tool that validates agent_name against allowed_agents before
            calling update_should_act action.
        """

        def handler(payload: dict[str, Any]) -> None:
            agent_name = payload["agent_name"]
            if allowed_agents != "all" and agent_name not in allowed_agents:
                raise ValueError(
                    f"Agent '{agent_name}' is not in allowed agents: {allowed_agents}"
                )
            # Cast to UpdateShouldActPayload - validation happens via JSON schema
            self._store.update_should_act(payload)  # type: ignore[arg-type]

        return Tool(
            name="update_should_act",
            description="Update an agent's should_act flag. Use to signal completion or activate other agents.",
            json_schema=JSONSchema({
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "should_act": {"type": "boolean"},
                },
                "required": ["agent_name", "should_act"],
            }),
            handler=handler,
        )

    def run_once(self) -> None:
        """Run one iteration of the agent loop.

        Checks all agents for should_act=True, calls step() on each active agent,
        and executes the tool calls they return.

        This should be called repeatedly (e.g., in a while loop) to drive agent execution.
        """
        for agent_name, agent in self._agents.items():
            state = self.get_agent_state(agent_name)
            if state and state.should_act:
                tool_calls = agent.step()

                # Execute each tool call
                for tool_call in tool_calls:
                    tool_name = tool_call["tool_name"]
                    payload = tool_call["payload"]
                    tool = self._tools[agent_name][tool_name]

                    # TODO
                    # schema = json.loads(tool.to_metadata().json_schema)
                    # jsonschema.validate(payload, schema)
                    tool(payload)

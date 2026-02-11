"""AgentApp - manages agent lifecycle, separate from Store.

AgentApp holds Agent instances outside of Store, maintaining the security boundary
that prevents StoreUpdaters from accessing Agent behavior directly. It also holds tool
handlers and executes tool calls returned by agents.
"""

# pyright: reportPrivateUsage=false
# AgentApp needs access to Store internals (_state) to manage agent lifecycle.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from agent_lib.agent.Agent import Agent, PostProcessResponseFn
from agent_lib.agent.LLMClient import LLMClient
from agent_lib.context.components.ChatMessages import ChatMessages, ChatMessagesProps
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps
from agent_lib.store.snapshot import snapshot
from agent_lib.store.state.AgentState import AgentState
from agent_lib.store.Subscribers import Subscribers
from agent_lib.store.state.State import State
from agent_lib.store.updaters.update_agent_state import update_agent_state
from agent_lib.store.updaters.update_should_act import (
    UpdateShouldActPayload,
    update_should_act,
)
from agent_lib.tool.Tool import Tool


if TYPE_CHECKING:
    from agent_lib.store.Store import Store
    from agent_lib.store.StoreUpdaterBase import StoreUpdaterBase


class AgentApp[StateT: State]:
    """Manages agent lifecycle, separate from Store.

    AgentApp maintains the security boundary between agent data (in Store._state.agent_state)
    and agent behavior (Agent instances held here). StoreUpdaters receive the Store but cannot
    access AgentApp or Agent instances.

    Tool handlers are stored in the app while tool metadata lives in agent state.
    When an agent returns tool calls from step(), the app executes them using the stored handlers.

    Subscribers are managed by AgentApp (moved from Store) to keep Store focused on state.

    Usage:
        store = MyStore()
        app = AgentApp(store)

        # Create an agent - adds state to Store and creates Agent instance
        planner = app.create_agent("planner", llm_client, system_prompt)

        # Grant tools to the agent (metadata goes to state, handler stays in app)
        app.grant_tool("planner", some_tool)

        # Create a StoreUpdater and grant it
        @store_updater
        def set_value(store: MyStore, value: str) -> frozenset[str]:
            store._state.value = value
            return frozenset({"_state.value"})

        set_value.bind(app)
        app.grant_tool("planner", set_value)

        # Run the agent loop
        app.run()
    """

    _store: Store[StateT]
    _agents: dict[str, Agent]
    _tools: dict[str, dict[str, Any]]  # agent_name -> tool_name -> Tool|StoreUpdater
    subscribers: Subscribers

    def __init__(self, name: str, store: Store[StateT]) -> None:
        """Create an AgentApp managing agents for the given Store.

        Args:
            store: The Store whose agent_state this app manages
        """
        self.name = name
        self._store = store
        self._agents = {}
        self._tools = {}
        self.subscribers = Subscribers()
        self.update_agent_state = update_agent_state.bind(self)
        # Connect the store to the subscribers
        self._store.notify = lambda delta: self.subscribers.notify(delta)

    @property
    def state(self) -> StateT:
        """Convinence property to get a state snapshot directly from the app instance."""
        return self._store.state

    def create_agent(
        self,
        name: str,
        llm_client: LLMClient,
        system_prompt: CtxComponent[NoProps],
        messages: CtxComponent[NoProps] | None = None,
        state_class: type[AgentState] = AgentState,
        post_process_response: PostProcessResponseFn | None = None,
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
            post_process_response: Optional callback to transform LLM response before validation. Use this to wrap raw text responses as tool calls.
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

        # Create agent state and add to Store
        agent_state = state_class(agent_name=name, **state_kwargs)
        self.update_agent_state(agent_state)

        # Initialize tool storage for this agent
        self._tools[name] = {}

        # Create messages component - use provided or default to ChatMessages
        if messages is None:
            messages = self._store.connect(
                ChatMessages,
                lambda s, n=name: ChatMessagesProps(history=s.agent_state[n].history),
            )

        # Create context (connected to store, renders dynamically)
        context = LLMContext(system_prompt=system_prompt, messages=messages)

        # Create state selector for read-only access
        def get_state() -> AgentState:
            agent_state = self.get_agent_state(name)
            if not agent_state:
                raise ValueError(
                    f"The state for agent {name} was requesed using its getter but no state for this agent was found."
                )
            print("Agent state from getter")
            print(agent_state)
            return agent_state

        # Create Agent instance (held here, not in Store)
        agent = Agent(
            name=name,
            llm_client=llm_client,
            context=context,
            get_state=get_state,
            post_process_response=post_process_response,
        )
        self._agents[name] = agent

        # Grant should_act tool if access is specified (empty frozenset is falsy, "all" is truthy)
        if should_act_access:
            tool = self.make_should_act_tool(should_act_access)
            self.grant_tool(name, tool)

        return agent

    def grant_tool(self, agent_name: str, tool: Tool[Any, Any]) -> None:
        """Grant a tool to an agent.

        Adds tool metadata to agent's state and stores the handler in the app.
        If the tool is a StoreUpdaterBase, it will be automatically bound to this app.

        Args:
            agent_name: Name of the agent to grant the tool to
            tool: The tool to grant

        Raises:
            KeyError: If the agent doesn't exist
        """
        if agent_name not in self._agents:
            raise KeyError(f"Agent '{agent_name}' does not exist")

        # Auto-bind StoreUpdaters - import here to avoid circular import
        from agent_lib.store.StoreUpdaterBase import StoreUpdaterBase

        if isinstance(tool, StoreUpdaterBase):
            tool = tool.bind(self)

        # Add metadata to agent state
        metadata = tool.to_metadata()

        agent_state = self.state.agent_state

        if agent_name not in agent_state:
            raise ValueError(
                f"Attempting to grant tool for {agent_name}, but this agent does not exist in the agent state."
            )

        agent = agent_state[agent_name]
        agent.tools.append(metadata)
        self.update_agent_state(agent)

        # Store handler in app
        self._tools[agent_name][tool.name] = tool

    def revoke_tool(self, agent_name: str, tool_name: str) -> None:
        """Revoke a tool from an agent.

        Removes tool metadata from agent's state and removes the handler from the app.

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

        agent_state = self.state.agent_state

        if agent_name not in agent_state:
            # If agent does not exist in state, then no tool to remove
            return None

        agent = agent_state[agent_name]
        agent.tools = [t for t in agent.tools if t.name != tool_name]
        self.update_agent_state(agent)

        # Remove handler from app
        del self._tools[agent_name][tool_name]

    def get_agent(self, name: str) -> Agent | None:
        """Get an agent by name, or None if not found."""
        return self._agents.get(name)

    def get_agent_state(self, name: str) -> AgentState | None:
        """Get an agent's state from the Store, or None if not found. Avoids copying the entire state to get the snapshot of the agent's state."""
        return snapshot(self._store._state.agent_state.get(name))

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
        self.update_agent_state(name)

    def list_agents(self) -> list[str]:
        """List the names of all agents."""
        return list(self._agents.keys())

    def make_should_act_tool(
        self,
        allowed_agents: frozenset[str] | Literal["all"],
    ) -> StoreUpdaterBase[StateT, UpdateShouldActPayload]:
        """Create a should_act tool with constrained agent access.

        Returns a copy of the update_should_act StoreUpdater that validates
        agent_name against the allowed_agents list.

        Args:
            allowed_agents: Either "all" to allow updating any agent,
                or a frozenset of agent names that can be updated.

        Returns:
            A StoreUpdater that validates agent_name against allowed_agents before
            calling the underlying update_should_act updater.
        """
        updater = update_should_act.bind(self)

        def validator(payload: UpdateShouldActPayload) -> Literal[True] | str:
            agent_name = payload["agent_name"]
            if allowed_agents != "all" and agent_name not in allowed_agents:
                return (
                    f"Agent '{agent_name}' is not in allowed agents: {allowed_agents}"
                )
            else:
                return True

        updater.validator = validator

        return updater

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

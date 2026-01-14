"""Tests for AgentRuntime class."""

# pyright: reportPrivateUsage=false
# Tests need access to Store internals to verify behavior.

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agent_lib.agent.Agent import Agent
from agent_lib.agent.AgentRuntime import AgentRuntime
from agent_lib.agent.AgentState import AgentState
from agent_lib.agent.Tool import Tool
from agent_lib.store.State import State
from agent_lib.store.Store import Store


class TestAgentCreation:
    """Tests for creating agents via AgentRuntime."""

    def test_create_agent_basic(self) -> None:
        """Creating an agent adds state to Store and returns Agent."""
        store = Store()
        runtime = AgentRuntime(store)

        agent = runtime.create_agent("planner")

        assert isinstance(agent, Agent)
        assert agent.name == "planner"
        assert "planner" in store._state.agent_state
        assert store._state.agent_state["planner"] is agent.state

    def test_create_agent_with_custom_state_class(self) -> None:
        """Can create agent with custom AgentState subclass."""

        @dataclass
        class PlannerState(AgentState):
            plan: list[str] = field(default_factory=list)

        store = Store()
        runtime = AgentRuntime(store)

        agent = runtime.create_agent("planner", state_class=PlannerState)

        assert isinstance(agent.state, PlannerState)
        assert agent.state.plan == []

    def test_create_duplicate_agent_raises(self) -> None:
        """Creating agent with existing name raises ValueError."""
        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent("planner")

        with pytest.raises(ValueError, match="already exists"):
            runtime.create_agent("planner")


class TestAgentRetrieval:
    """Tests for getting agents."""

    def test_get_agent_exists(self) -> None:
        """get_agent returns the agent if it exists."""
        store = Store()
        runtime = AgentRuntime(store)
        created = runtime.create_agent("planner")

        retrieved = runtime.get_agent("planner")

        assert retrieved is created

    def test_get_agent_not_exists(self) -> None:
        """get_agent returns None if agent doesn't exist."""
        store = Store()
        runtime = AgentRuntime(store)

        assert runtime.get_agent("nonexistent") is None


class TestAgentRemoval:
    """Tests for removing agents."""

    def test_remove_agent(self) -> None:
        """Removing agent deletes it from runtime and Store."""
        store = Store()
        runtime = AgentRuntime(store)
        runtime.create_agent("planner")

        runtime.remove_agent("planner")

        assert runtime.get_agent("planner") is None
        assert "planner" not in store._state.agent_state

    def test_remove_nonexistent_agent_raises(self) -> None:
        """Removing nonexistent agent raises KeyError."""
        store = Store()
        runtime = AgentRuntime(store)

        with pytest.raises(KeyError, match="does not exist"):
            runtime.remove_agent("nonexistent")


class TestListAgents:
    """Tests for listing agents."""

    def test_list_agents_empty(self) -> None:
        """New runtime has no agents."""
        store = Store()
        runtime = AgentRuntime(store)

        assert runtime.list_agents() == []

    def test_list_agents(self) -> None:
        """list_agents returns names of all agents."""
        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent("planner")
        runtime.create_agent("executor")

        agents = runtime.list_agents()
        assert set(agents) == {"planner", "executor"}


class TestActionToTool:
    """Tests for wrapping Store actions as Tools."""

    def test_action_to_tool_basic(self) -> None:
        """action_to_tool wraps a Store action."""

        class CounterStore(Store):
            count: int = 0

            @Store.action
            def increment(self, amount: int) -> frozenset[str]:
                self.count += amount
                return frozenset({"count"})

        store = CounterStore()
        runtime = AgentRuntime(store)

        tool = runtime.action_to_tool("increment", description="Add to counter")

        assert tool.name == "increment"
        assert tool.description == "Add to counter"

    def test_action_to_tool_invocation(self) -> None:
        """Invoking the tool triggers the Store action."""

        class CounterStore(Store):
            count: int = 0

            @Store.action
            def increment(self, amount: int) -> frozenset[str]:
                self.count += amount
                return frozenset({"count"})

        store = CounterStore()
        runtime = AgentRuntime(store)
        agent = runtime.create_agent("agent")

        tool = runtime.action_to_tool("increment")
        agent.grant_tool(tool)

        agent.invoke("increment", 5)

        assert store.count == 5

    def test_action_to_tool_nonexistent_raises(self) -> None:
        """action_to_tool raises KeyError for nonexistent action."""
        store = Store()
        runtime = AgentRuntime(store)

        with pytest.raises(KeyError, match="does not exist"):
            runtime.action_to_tool("nonexistent")


class TestMakeTool:
    """Tests for make_tool convenience method."""

    def test_make_tool(self) -> None:
        """make_tool creates a custom Tool."""
        store = Store()
        runtime = AgentRuntime(store)

        tool = runtime.make_tool(
            name="greet",
            description="Greet someone",
            json_schema="{}",
            handler=lambda name: f"Hello, {name}!",
        )

        assert tool.name == "greet"
        assert tool("World") == "Hello, World!"


class TestSecurityBoundary:
    """Tests verifying the security boundary between Store and Agent instances."""

    def test_store_cannot_access_agents(self) -> None:
        """Store has no reference to AgentRuntime or Agent instances."""
        store = Store()
        runtime = AgentRuntime(store)
        runtime.create_agent("planner")

        # Store has agent_state (data) but not Agent instances
        assert hasattr(store._state, "agent_state")
        assert "planner" in store._state.agent_state

        # Store should NOT have any way to access the Agent instance
        assert not hasattr(store, "_runtime")
        assert not hasattr(store, "agents")
        assert not hasattr(store._state, "agents")

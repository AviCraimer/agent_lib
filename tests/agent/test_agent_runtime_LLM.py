"""Tests for AgentRuntime class."""

# pyright: reportPrivateUsage=false
# Tests need access to Store internals to verify behavior.

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agent_lib.agent.Agent import Agent
from agent_lib.agent_app.AgentRuntime import AgentRuntime
from agent_lib.store.state.AgentState import AgentState
from agent_lib.tool.Tool import Tool
from agent_lib.tool.ToolMetadata import ToolMetadata
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps
from agent_lib.store.Store import Store


class MockLLMClient:
    """Mock LLM client for testing."""

    message_json_schema: str = "{}"

    def __init__(self, response: str = '{"tool_calls": []}'):
        self.response = response

    def get_response(self, context: LLMContext) -> str:
        return self.response


def mock_system_prompt() -> CtxComponent[NoProps]:
    """Create a mock system prompt component for testing."""
    return CtxComponent.leaf(lambda: "Test system prompt")


class TestAgentCreation:
    """Tests for creating agents via AgentRuntime."""

    def test_create_agent_basic(self) -> None:
        """Creating an agent adds state to Store and returns Agent."""
        store = Store()
        runtime = AgentRuntime(store)

        agent = runtime.create_agent("planner", MockLLMClient(), mock_system_prompt())

        assert isinstance(agent, Agent)
        assert agent.name == "planner"
        assert "planner" in store._state.agent_state
        assert runtime.get_agent_state("planner") is store._state.agent_state["planner"]

    def test_create_agent_with_custom_state_class(self) -> None:
        """Can create agent with custom AgentState subclass."""

        @dataclass
        class PlannerState(AgentState):
            plan: list[str] = field(default_factory=list)

        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent(
            "planner", MockLLMClient(), mock_system_prompt(), state_class=PlannerState
        )
        state = runtime.get_agent_state("planner")

        assert isinstance(state, PlannerState)
        assert state.plan == []

    def test_create_duplicate_agent_raises(self) -> None:
        """Creating agent with existing name raises ValueError."""
        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent("planner", MockLLMClient(), mock_system_prompt())

        with pytest.raises(ValueError, match="already exists"):
            runtime.create_agent("planner", MockLLMClient(), mock_system_prompt())


class TestAgentRetrieval:
    """Tests for getting agents."""

    def test_get_agent_exists(self) -> None:
        """get_agent returns the agent if it exists."""
        store = Store()
        runtime = AgentRuntime(store)
        created = runtime.create_agent("planner", MockLLMClient(), mock_system_prompt())

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
        runtime.create_agent("planner", MockLLMClient(), mock_system_prompt())

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

        runtime.create_agent("planner", MockLLMClient(), mock_system_prompt())
        runtime.create_agent("executor", MockLLMClient(), mock_system_prompt())

        agents = runtime.list_agents()
        assert set(agents) == {"planner", "executor"}


class TestGrantTool:
    """Tests for granting tools to agents via AgentRuntime."""

    def test_grant_tool_adds_metadata_to_state(self) -> None:
        """grant_tool adds tool metadata to agent's state."""
        store = Store()
        runtime = AgentRuntime(store)
        runtime.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = Tool("greet", "Greet someone", "{}", lambda x: f"Hello, {x}")
        runtime.grant_tool("agent", tool)

        state = runtime.get_agent_state("agent")
        assert state is not None
        assert len(state.tools) == 1
        assert state.tools[0].name == "greet"
        assert isinstance(state.tools[0], ToolMetadata)

    def test_grant_tool_stores_handler_in_runtime(self) -> None:
        """grant_tool stores the tool handler in the runtime."""
        store = Store()
        runtime = AgentRuntime(store)
        runtime.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = Tool("greet", "Greet someone", "{}", lambda x: f"Hello, {x}")
        runtime.grant_tool("agent", tool)

        # Handler should be accessible via runtime's internal storage
        assert "agent" in runtime._tools
        assert "greet" in runtime._tools["agent"]
        assert runtime._tools["agent"]["greet"] is tool

    def test_grant_tool_nonexistent_agent_raises(self) -> None:
        """grant_tool raises KeyError for nonexistent agent."""
        store = Store()
        runtime = AgentRuntime(store)

        tool = Tool("greet", "Greet someone", "{}", lambda x: f"Hello, {x}")

        with pytest.raises(KeyError, match="does not exist"):
            runtime.grant_tool("nonexistent", tool)


class TestRevokeTool:
    """Tests for revoking tools from agents via AgentRuntime."""

    def test_revoke_tool_removes_from_state_and_runtime(self) -> None:
        """revoke_tool removes tool from both state and runtime."""
        store = Store()
        runtime = AgentRuntime(store)
        runtime.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = Tool("greet", "Greet someone", "{}", lambda x: f"Hello, {x}")
        runtime.grant_tool("agent", tool)
        runtime.revoke_tool("agent", "greet")

        state = runtime.get_agent_state("agent")
        assert state is not None
        assert len(state.tools) == 0
        assert "greet" not in runtime._tools["agent"]

    def test_revoke_tool_nonexistent_agent_raises(self) -> None:
        """revoke_tool raises KeyError for nonexistent agent."""
        store = Store()
        runtime = AgentRuntime(store)

        with pytest.raises(KeyError, match="does not exist"):
            runtime.revoke_tool("nonexistent", "greet")

    def test_revoke_tool_nonexistent_tool_raises(self) -> None:
        """revoke_tool raises KeyError for nonexistent tool."""
        store = Store()
        runtime = AgentRuntime(store)
        runtime.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        with pytest.raises(KeyError, match="not granted"):
            runtime.revoke_tool("agent", "nonexistent")


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
        runtime.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = runtime.action_to_tool("increment")
        runtime.grant_tool("agent", tool)

        # Invoke through the runtime's stored handler
        runtime._tools["agent"]["increment"](5)

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


class TestRun:
    """Tests for the run() method."""

    def test_run_calls_step_on_active_agents(self) -> None:
        """run() calls step() on agents with should_act=True."""
        calls: list[str] = []

        class TrackingLLMClient:
            message_json_schema: str = "{}"

            def __init__(self, name: str):
                self.name = name

            def get_response(self, context: LLMContext) -> str:
                calls.append(self.name)
                return '{"tool_calls": []}'

        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent(
            "active", TrackingLLMClient("active"), mock_system_prompt()
        )
        runtime.create_agent(
            "inactive", TrackingLLMClient("inactive"), mock_system_prompt()
        )

        # Set one agent to active
        store.update_should_act({"agent_name": "active", "should_act": True})

        runtime.run()

        assert calls == ["active"]

    def test_run_skips_inactive_agents(self) -> None:
        """run() does not call step() on agents with should_act=False."""
        calls: list[str] = []

        class TrackingLLMClient:
            message_json_schema: str = "{}"

            def __init__(self, name: str):
                self.name = name

            def get_response(self, context: LLMContext) -> str:
                calls.append(self.name)
                return '{"tool_calls": []}'

        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent(
            "agent1", TrackingLLMClient("agent1"), mock_system_prompt()
        )
        runtime.create_agent(
            "agent2", TrackingLLMClient("agent2"), mock_system_prompt()
        )

        # Both agents have should_act=False by default
        runtime.run()

        assert calls == []

    def test_run_executes_tool_calls(self) -> None:
        """run() executes tool calls from active agents."""
        results: list[str] = []

        class ToolCallingLLMClient:
            message_json_schema: str = "{}"

            def get_response(self, context: LLMContext) -> str:
                return '{"tool_calls": [{"tool_name": "record", "payload": {"value": "executed"}}]}'

        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent("agent", ToolCallingLLMClient(), mock_system_prompt())
        tool = Tool(
            "record", "Record a value", "{}", lambda p: results.append(p["value"])
        )
        runtime.grant_tool("agent", tool)

        store.update_should_act({"agent_name": "agent", "should_act": True})
        runtime.run()

        assert results == ["executed"]


class TestSecurityBoundary:
    """Tests verifying the security boundary between Store and Agent instances."""

    def test_store_cannot_access_agents(self) -> None:
        """Store has no reference to AgentRuntime or Agent instances."""
        store = Store()
        runtime = AgentRuntime(store)
        runtime.create_agent("planner", MockLLMClient(), mock_system_prompt())

        # Store has agent_state (data) but not Agent instances
        assert hasattr(store._state, "agent_state")
        assert "planner" in store._state.agent_state

        # Store should NOT have any way to access the Agent instance
        assert not hasattr(store, "_runtime")
        assert not hasattr(store, "agents")
        assert not hasattr(store._state, "agents")

    def test_tool_metadata_in_state_handler_in_runtime(self) -> None:
        """Tool metadata is in state, handler is in runtime only."""
        store = Store()
        runtime = AgentRuntime(store)
        runtime.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = Tool("greet", "Greet someone", "{}", lambda x: f"Hello, {x}")
        runtime.grant_tool("agent", tool)

        state = runtime.get_agent_state("agent")
        assert state is not None

        # State has metadata (no handler)
        tool_metadata = state.tools[0]
        assert isinstance(tool_metadata, ToolMetadata)
        assert not hasattr(tool_metadata, "handler")

        # Runtime has full tool (with handler)
        runtime_tool = runtime._tools["agent"]["greet"]
        assert hasattr(runtime_tool, "handler")


class TestShouldActAccess:
    """Tests for constrained should_act tool access."""

    def test_should_act_tool_all_access(self) -> None:
        """should_act_access='all' allows updating any agent."""
        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent(
            "agent1", MockLLMClient(), mock_system_prompt(), should_act_access="all"
        )
        runtime.create_agent(
            "agent2",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # agent1 should be able to update agent2
        tool = runtime._tools["agent1"]["update_should_act"]
        tool({"agent_name": "agent2", "should_act": True})

        assert store._state.agent_state["agent2"].should_act is True

    def test_should_act_tool_restricted_access(self) -> None:
        """should_act_access with frozenset restricts to named agents."""
        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent(
            "agent1",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset({"agent2"}),
        )
        runtime.create_agent(
            "agent2",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )
        runtime.create_agent(
            "agent3",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # agent1 can update agent2
        tool = runtime._tools["agent1"]["update_should_act"]
        tool({"agent_name": "agent2", "should_act": True})
        assert store._state.agent_state["agent2"].should_act is True

        # agent1 cannot update agent3
        with pytest.raises(ValueError, match="not in allowed agents"):
            tool({"agent_name": "agent3", "should_act": True})

    def test_should_act_tool_self_only(self) -> None:
        """should_act_access with just self name restricts to self."""
        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent(
            "agent1",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset({"agent1"}),
        )
        runtime.create_agent(
            "agent2",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # agent1 can update itself
        tool = runtime._tools["agent1"]["update_should_act"]
        tool({"agent_name": "agent1", "should_act": True})
        assert store._state.agent_state["agent1"].should_act is True

        # agent1 cannot update agent2
        with pytest.raises(ValueError, match="not in allowed agents"):
            tool({"agent_name": "agent2", "should_act": True})

    def test_should_act_tool_empty_set_no_tool(self) -> None:
        """Empty frozenset grants no should_act tool."""
        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # No update_should_act tool should be granted
        assert "update_should_act" not in runtime._tools["agent"]
        state = runtime.get_agent_state("agent")
        assert state is not None
        assert len([t for t in state.tools if t.name == "update_should_act"]) == 0

    def test_should_act_tool_unauthorized_raises(self) -> None:
        """ValueError raised when target agent not in allowed set."""
        store = Store()
        runtime = AgentRuntime(store)

        runtime.create_agent(
            "agent1",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset({"agent1"}),
        )
        runtime.create_agent(
            "agent2",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = runtime._tools["agent1"]["update_should_act"]

        with pytest.raises(ValueError, match="not in allowed agents"):
            tool({"agent_name": "agent2", "should_act": True})

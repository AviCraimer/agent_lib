"""Tests for AgentApp class."""

# pyright: reportPrivateUsage=false
# Tests need access to Store internals to verify behavior.

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agent_lib.agent.Agent import Agent
from agent_lib.agent_app.AgentApp import AgentApp
from agent_lib.store.state.AgentState import AgentState
from agent_lib.store.StoreUpdater import StoreUpdater
from agent_lib.tool.Tool import Tool
from agent_lib.tool.ToolMetadata import ToolMetadata
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps
from agent_lib.store.Store import Store
from agent_lib.util.json_utils import JSONSchema


class MockLLMClient:
    """Mock LLM client for testing."""

    message_json_schema: JSONSchema = JSONSchema({})

    def __init__(self, response: str = "[]"):
        self.response = response

    def get_response(self, context: LLMContext) -> str:
        return self.response


def mock_system_prompt() -> CtxComponent[NoProps]:
    """Create a mock system prompt component for testing."""
    return CtxComponent.leaf(lambda: "Test system prompt")


class TestAgentCreation:
    """Tests for creating agents via AgentApp."""

    def test_create_agent_basic(self) -> None:
        """Creating an agent adds state to Store and returns Agent."""
        store = Store()
        app = AgentApp(store)

        agent = app.create_agent("planner", MockLLMClient(), mock_system_prompt())

        assert isinstance(agent, Agent)
        assert agent.name == "planner"
        assert "planner" in store.state.agent_state
        assert app.get_agent_state("planner") is store.state.agent_state["planner"]

    def test_create_agent_with_custom_state_class(self) -> None:
        """Can create agent with custom AgentState subclass."""

        @dataclass
        class PlannerState(AgentState):
            plan: list[str] = field(default_factory=list)

        store = Store()
        app = AgentApp(store)

        app.create_agent(
            "planner", MockLLMClient(), mock_system_prompt(), state_class=PlannerState
        )
        state = app.get_agent_state("planner")

        assert isinstance(state, PlannerState)
        assert state.plan == []

    def test_create_duplicate_agent_raises(self) -> None:
        """Creating agent with existing name raises ValueError."""
        store = Store()
        app = AgentApp(store)

        app.create_agent("planner", MockLLMClient(), mock_system_prompt())

        with pytest.raises(ValueError, match="already exists"):
            app.create_agent("planner", MockLLMClient(), mock_system_prompt())


class TestAgentRetrieval:
    """Tests for getting agents."""

    def test_get_agent_exists(self) -> None:
        """get_agent returns the agent if it exists."""
        store = Store()
        app = AgentApp(store)
        created = app.create_agent("planner", MockLLMClient(), mock_system_prompt())

        retrieved = app.get_agent("planner")

        assert retrieved is created

    def test_get_agent_not_exists(self) -> None:
        """get_agent returns None if agent doesn't exist."""
        store = Store()
        app = AgentApp(store)

        assert app.get_agent("nonexistent") is None


class TestAgentRemoval:
    """Tests for removing agents."""

    def test_remove_agent(self) -> None:
        """Removing agent deletes it from app and Store."""
        store = Store()
        app = AgentApp(store)
        app.create_agent("planner", MockLLMClient(), mock_system_prompt())

        app.remove_agent("planner")

        assert app.get_agent("planner") is None
        assert "planner" not in store.state.agent_state

    def test_remove_nonexistent_agent_raises(self) -> None:
        """Removing nonexistent agent raises KeyError."""
        store = Store()
        app = AgentApp(store)

        with pytest.raises(KeyError, match="does not exist"):
            app.remove_agent("nonexistent")


class TestListAgents:
    """Tests for listing agents."""

    def test_list_agents_empty(self) -> None:
        """New app has no agents."""
        store = Store()
        app = AgentApp(store)

        assert app.list_agents() == []

    def test_list_agents(self) -> None:
        """list_agents returns names of all agents."""
        store = Store()
        app = AgentApp(store)

        app.create_agent("planner", MockLLMClient(), mock_system_prompt())
        app.create_agent("executor", MockLLMClient(), mock_system_prompt())

        agents = app.list_agents()
        assert set(agents) == {"planner", "executor"}


class TestGrantTool:
    """Tests for granting tools to agents via AgentApp."""

    def test_grant_tool_adds_metadata_to_state(self) -> None:
        """grant_tool adds tool metadata to agent's state."""
        store = Store()
        app = AgentApp(store)
        app.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = Tool[str, str](
            "greet", "Greet someone", JSONSchema({}), lambda x: f"Hello, {x}"
        )
        app.grant_tool("agent", tool)

        state = app.get_agent_state("agent")
        assert state is not None
        assert len(state.tools) == 1
        assert state.tools[0].name == "greet"
        assert isinstance(state.tools[0], ToolMetadata)

    def test_grant_tool_stores_handler_in_app(self) -> None:
        """grant_tool stores the tool handler in the app."""
        store = Store()
        app = AgentApp(store)
        app.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = Tool[str, str](
            "greet", "Greet someone", JSONSchema({}), lambda x: f"Hello, {x}"
        )
        app.grant_tool("agent", tool)

        # Handler should be accessible via app's internal storage
        assert "agent" in app._tools
        assert "greet" in app._tools["agent"]
        assert app._tools["agent"]["greet"] is tool

    def test_grant_tool_nonexistent_agent_raises(self) -> None:
        """grant_tool raises KeyError for nonexistent agent."""
        store = Store()
        app = AgentApp(store)

        tool = Tool[str, str](
            "greet", "Greet someone", JSONSchema({}), lambda x: f"Hello, {x}"
        )

        with pytest.raises(KeyError, match="does not exist"):
            app.grant_tool("nonexistent", tool)


class TestRevokeTool:
    """Tests for revoking tools from agents via AgentApp."""

    def test_revoke_tool_removes_from_state_and_app(self) -> None:
        """revoke_tool removes tool from both state and app."""
        store = Store()
        app = AgentApp(store)
        app.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = Tool[str, str](
            "greet", "Greet someone", JSONSchema({}), lambda x: f"Hello, {x}"
        )
        app.grant_tool("agent", tool)
        app.revoke_tool("agent", "greet")

        state = app.get_agent_state("agent")
        assert state is not None
        assert len(state.tools) == 0
        assert "greet" not in app._tools["agent"]

    def test_revoke_tool_nonexistent_agent_raises(self) -> None:
        """revoke_tool raises KeyError for nonexistent agent."""
        store = Store()
        app = AgentApp(store)

        with pytest.raises(KeyError, match="does not exist"):
            app.revoke_tool("nonexistent", "greet")

    def test_revoke_tool_nonexistent_tool_raises(self) -> None:
        """revoke_tool raises KeyError for nonexistent tool."""
        store = Store()
        app = AgentApp(store)
        app.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        with pytest.raises(KeyError, match="not granted"):
            app.revoke_tool("agent", "nonexistent")


class TestStoreUpdaterGrant:
    """Tests for granting StoreUpdaters to agents."""

    def test_store_updater_auto_binds(self) -> None:
        """StoreUpdater is automatically bound when granted."""

        class CounterStore(Store):
            count: int = 0

        def _increment_handler(store: CounterStore, amount: int) -> frozenset[str]:
            store.count += amount
            return frozenset({"count"})

        increment = StoreUpdater[int, CounterStore](
            name="increment",
            description="Add to counter",
            payload_json_schema=JSONSchema({}),
            updater=_increment_handler,
        )

        store = CounterStore()
        app = AgentApp(store)
        app.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # Before granting, not bound
        assert increment._app is None

        app.grant_tool("agent", increment)

        # After granting, should be bound
        assert increment._app is app
        assert increment._store is store

    def test_store_updater_invocation(self) -> None:
        """Invoking the StoreUpdater mutates state."""

        class CounterStore(Store):
            count: int = 0

        def _increment_handler(store: CounterStore, amount: int) -> frozenset[str]:
            store.count += amount
            return frozenset({"count"})

        increment = StoreUpdater[int, CounterStore](
            name="increment",
            description="Add to counter",
            payload_json_schema=JSONSchema({}),
            updater=_increment_handler,
        )

        store = CounterStore()
        app = AgentApp(store)
        app.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        app.grant_tool("agent", increment)

        # Invoke through the app's stored handler
        app._tools["agent"]["increment"](5)

        assert store.count == 5


class TestRun:
    """Tests for the run_once() method."""

    def test_run_calls_step_on_active_agents(self) -> None:
        """run_once() calls step() on agents with should_act=True."""
        calls: list[str] = []

        class TrackingLLMClient:
            message_json_schema: JSONSchema = JSONSchema({})

            def __init__(self, name: str):
                self.name = name

            def get_response(self, context: LLMContext) -> str:
                calls.append(self.name)
                return "[]"

        store = Store()
        app = AgentApp(store)

        app.create_agent("active", TrackingLLMClient("active"), mock_system_prompt())
        app.create_agent(
            "inactive", TrackingLLMClient("inactive"), mock_system_prompt()
        )

        # Set one agent to active via the update_should_act updater
        from agent_lib.store.updaters.update_should_act import update_should_act

        update_should_act.bind(app)
        update_should_act({"agent_name": "active", "should_act": True})

        app.run_once()

        assert calls == ["active"]

    def test_run_skips_inactive_agents(self) -> None:
        """run_once() does not call step() on agents with should_act=False."""
        calls: list[str] = []

        class TrackingLLMClient:
            message_json_schema: JSONSchema = JSONSchema({})

            def __init__(self, name: str):
                self.name = name

            def get_response(self, context: LLMContext) -> str:
                calls.append(self.name)
                return "[]"

        store = Store()
        app = AgentApp(store)

        app.create_agent("agent1", TrackingLLMClient("agent1"), mock_system_prompt())
        app.create_agent("agent2", TrackingLLMClient("agent2"), mock_system_prompt())

        # Both agents have should_act=False by default
        app.run_once()

        assert calls == []

    def test_run_executes_tool_calls(self) -> None:
        """run_once() executes tool calls from active agents."""
        results: list[str] = []

        class ToolCallingLLMClient:
            message_json_schema: JSONSchema = JSONSchema({})

            def get_response(self, context: LLMContext) -> str:
                return '[{"tool_name": "record", "payload": {"value": "executed"}}]'

        store = Store()
        app = AgentApp(store)

        app.create_agent("agent", ToolCallingLLMClient(), mock_system_prompt())
        tool: Tool[dict[str, str], None] = Tool(
            "record",
            "Record a value",
            JSONSchema({}),
            lambda p: results.append(p["value"]),
        )
        app.grant_tool("agent", tool)

        from agent_lib.store.updaters.update_should_act import update_should_act

        update_should_act.bind(app)
        update_should_act({"agent_name": "agent", "should_act": True})
        app.run_once()

        assert results == ["executed"]


class TestSecurityBoundary:
    """Tests verifying the security boundary between Store and Agent instances."""

    def test_store_cannot_access_agents(self) -> None:
        """Store has no reference to AgentApp or Agent instances."""
        store = Store()
        app = AgentApp(store)
        app.create_agent("planner", MockLLMClient(), mock_system_prompt())

        # Store has agent_state (data) but not Agent instances
        assert hasattr(store.state, "agent_state")
        assert "planner" in store.state.agent_state

        # Store should NOT have any way to access the Agent instance
        assert not hasattr(store, "_app")
        assert not hasattr(store, "agents")
        assert not hasattr(store.state, "agents")

    def test_tool_metadata_in_state_handler_in_app(self) -> None:
        """Tool metadata is in state, handler is in app only."""
        store = Store()
        app = AgentApp(store)
        app.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = Tool("greet", "Greet someone", JSONSchema({}), lambda x: f"Hello, {x}")
        app.grant_tool("agent", tool)

        state = app.get_agent_state("agent")
        assert state is not None

        # State has metadata (no handler)
        tool_metadata = state.tools[0]
        assert isinstance(tool_metadata, ToolMetadata)
        assert not hasattr(tool_metadata, "handler")

        # App has full tool (with handler)
        app_tool = app._tools["agent"]["greet"]
        assert hasattr(app_tool, "handler")


class TestShouldActAccess:
    """Tests for constrained should_act tool access."""

    def test_should_act_tool_all_access(self) -> None:
        """should_act_access='all' allows updating any agent."""
        store = Store()
        app = AgentApp(store)

        app.create_agent(
            "agent1", MockLLMClient(), mock_system_prompt(), should_act_access="all"
        )
        app.create_agent(
            "agent2",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # agent1 should be able to update agent2
        tool = app._tools["agent1"]["update_should_act"]
        tool({"agent_name": "agent2", "should_act": True})

        assert store.state.agent_state["agent2"].should_act is True

    def test_should_act_tool_restricted_access(self) -> None:
        """should_act_access with frozenset restricts to named agents."""
        store = Store()
        app = AgentApp(store)

        app.create_agent(
            "agent1",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset({"agent2"}),
        )
        app.create_agent(
            "agent2",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )
        app.create_agent(
            "agent3",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # agent1 can update agent2
        tool = app._tools["agent1"]["update_should_act"]
        tool({"agent_name": "agent2", "should_act": True})
        assert store.state.agent_state["agent2"].should_act is True

        # agent1 cannot update agent3
        with pytest.raises(ValueError, match="not in allowed agents"):
            tool({"agent_name": "agent3", "should_act": True})

    def test_should_act_tool_self_only(self) -> None:
        """should_act_access with just self name restricts to self."""
        store = Store()
        app = AgentApp(store)

        app.create_agent(
            "agent1",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset({"agent1"}),
        )
        app.create_agent(
            "agent2",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # agent1 can update itself
        tool = app._tools["agent1"]["update_should_act"]
        tool({"agent_name": "agent1", "should_act": True})
        assert store.state.agent_state["agent1"].should_act is True

        # agent1 cannot update agent2
        with pytest.raises(ValueError, match="not in allowed agents"):
            tool({"agent_name": "agent2", "should_act": True})

    def test_should_act_tool_empty_set_no_tool(self) -> None:
        """Empty frozenset grants no should_act tool."""
        store = Store()
        app = AgentApp(store)

        app.create_agent(
            "agent",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        # No update_should_act tool should be granted
        assert "update_should_act" not in app._tools["agent"]
        state = app.get_agent_state("agent")
        assert state is not None
        assert len([t for t in state.tools if t.name == "update_should_act"]) == 0

    def test_should_act_tool_unauthorized_raises(self) -> None:
        """ValueError raised when target agent not in allowed set."""
        store = Store()
        app = AgentApp(store)

        app.create_agent(
            "agent1",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset({"agent1"}),
        )
        app.create_agent(
            "agent2",
            MockLLMClient(),
            mock_system_prompt(),
            should_act_access=frozenset(),
        )

        tool = app._tools["agent1"]["update_should_act"]

        with pytest.raises(ValueError, match="not in allowed agents"):
            tool({"agent_name": "agent2", "should_act": True})

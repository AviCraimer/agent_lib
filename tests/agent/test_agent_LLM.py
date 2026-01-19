"""Tests for Agent class."""

from __future__ import annotations

import json

import pytest

from agent_lib.agent.Agent import Agent
from agent_lib.store.state.AgentState import AgentState
from agent_lib.tool.ToolMetadata import ToolMetadata
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.util.json_utils import JSONSchema


class MockLLMClient:
    """Mock LLM client for testing."""

    message_json_schema: JSONSchema = JSONSchema({})

    def __init__(self, response: str = '[]'):
        self.response = response
        self.last_context: LLMContext | None = None

    def get_response(self, context: LLMContext) -> str:
        self.last_context = context
        return self.response


def mock_context() -> LLMContext:
    """Create a mock LLMContext for testing."""
    return LLMContext(
        system_prompt=CtxComponent.leaf(lambda: ""),
        messages=CtxComponent.leaf(lambda: "[]"),
    )


def mock_state(tools: list[ToolMetadata] | None = None) -> AgentState:
    """Create a mock AgentState for testing."""
    state = AgentState(agent_name="agent")
    if tools:
        state.tools = tools
    return state


def make_get_state(state: AgentState):
    """Create a mock get_state function."""
    return lambda: state


class TestAgentCreation:
    """Tests for Agent initialization."""

    def test_create_agent(self) -> None:
        """Agent can be created with name, llm_client, context, and get_state."""
        mock_client = MockLLMClient()
        state = mock_state()
        agent = Agent(
            name="planner",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
        )

        assert agent.name == "planner"
        assert agent.llm_client is mock_client


class TestToolQueries:
    """Tests for querying tools via get_state."""

    def test_has_tool_true(self) -> None:
        """has_tool returns True when tool metadata is in state."""
        state = mock_state([ToolMetadata("greet", "Greet someone", JSONSchema({}))])
        agent = Agent(
            name="agent",
            llm_client=MockLLMClient(),
            context=mock_context(),
            get_state=make_get_state(state),
        )

        assert agent.has_tool("greet")

    def test_has_tool_false(self) -> None:
        """has_tool returns False when tool is not in state."""
        state = mock_state()
        agent = Agent(
            name="agent",
            llm_client=MockLLMClient(),
            context=mock_context(),
            get_state=make_get_state(state),
        )

        assert not agent.has_tool("greet")

    def test_list_tools_empty(self) -> None:
        """list_tools returns empty list when no tools in state."""
        state = mock_state()
        agent = Agent(
            name="agent",
            llm_client=MockLLMClient(),
            context=mock_context(),
            get_state=make_get_state(state),
        )

        assert agent.list_tools() == []

    def test_list_tools_with_tools(self) -> None:
        """list_tools returns names of tools in state."""
        state = mock_state(
            [
                ToolMetadata("a", "Tool A", JSONSchema({})),
                ToolMetadata("b", "Tool B", JSONSchema({})),
                ToolMetadata("c", "Tool C", JSONSchema({})),
            ]
        )
        agent = Agent(
            name="agent",
            llm_client=MockLLMClient(),
            context=mock_context(),
            get_state=make_get_state(state),
        )

        tools = agent.list_tools()
        assert set(tools) == {"a", "b", "c"}


class TestStep:
    """Tests for the step() method."""

    def test_step_calls_llm_client(self) -> None:
        """step() calls the LLM client with the agent's context."""
        mock_client = MockLLMClient('[]')
        context = mock_context()
        state = mock_state()
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=context,
            get_state=make_get_state(state),
        )

        agent.step()

        assert mock_client.last_context is context

    def test_step_returns_tool_calls(self) -> None:
        """step() returns the validated tool calls from LLM response."""
        state = mock_state([ToolMetadata("record", "Record a value", JSONSchema({}))])
        mock_client = MockLLMClient(
            '[{"tool_name": "record", "payload": {"value": "hello"}}]'
        )
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
        )

        tool_calls = agent.step()

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "record"
        assert tool_calls[0]["payload"] == {"value": "hello"}

    def test_step_returns_empty_list_for_no_tools(self) -> None:
        """step() returns empty list when LLM returns no tool calls."""
        state = mock_state()
        mock_client = MockLLMClient('[]')
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
        )

        tool_calls = agent.step()

        assert tool_calls == []

    def test_step_raises_on_invalid_json(self) -> None:
        """step() raises on invalid JSON response."""
        state = mock_state()
        mock_client = MockLLMClient("not json")
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
        )

        with pytest.raises(json.JSONDecodeError):
            agent.step()

    def test_step_raises_on_unknown_tool(self) -> None:
        """step() raises KeyError when tool is not in state."""
        state = mock_state()  # No tools
        mock_client = MockLLMClient(
            '[{"tool_name": "unknown", "payload": {}}]'
        )
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
        )

        with pytest.raises(KeyError, match="not granted"):
            agent.step()

    def test_step_returns_multiple_tool_calls(self) -> None:
        """step() returns all tool calls from LLM response."""
        state = mock_state(
            [
                ToolMetadata("tool_a", "Tool A", JSONSchema({})),
                ToolMetadata("tool_b", "Tool B", JSONSchema({})),
            ]
        )
        mock_client = MockLLMClient(
            '[{"tool_name": "tool_a", "payload": {"x": 1}}, {"tool_name": "tool_b", "payload": {"y": 2}}]'
        )
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
        )

        tool_calls = agent.step()

        assert len(tool_calls) == 2
        assert tool_calls[0]["tool_name"] == "tool_a"
        assert tool_calls[1]["tool_name"] == "tool_b"

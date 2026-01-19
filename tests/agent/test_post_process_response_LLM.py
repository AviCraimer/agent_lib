"""Tests for Agent.post_process_response and response_helpers."""

from __future__ import annotations

import json

from agent_lib.agent.Agent import Agent, PostProcessedResponse
from agent_lib.agent.response_helpers import reponse_as_single_tool_call
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.store.state.AgentState import AgentState
from agent_lib.tool.ToolMetadata import ToolMetadata
from agent_lib.util.json_utils import JSONSchema


class MockLLMClient:
    """Mock LLM client for testing."""

    message_json_schema: JSONSchema = JSONSchema({})

    def __init__(self, response: str = "[]"):
        self.response = response

    def get_response(self, context: LLMContext) -> str:
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


class TestPostProcessResponseDefault:
    """Tests for default post_process_response behavior."""

    def test_default_passes_through_response(self) -> None:
        """Default post_process_response returns the response unchanged."""
        state = mock_state()
        agent = Agent(
            name="agent",
            llm_client=MockLLMClient(),
            context=mock_context(),
            get_state=make_get_state(state),
        )

        result = agent.post_process_response("test response")
        assert result == "test response"

    def test_default_passes_through_json_response(self) -> None:
        """Default post_process_response returns JSON string unchanged."""
        state = mock_state()
        agent = Agent(
            name="agent",
            llm_client=MockLLMClient(),
            context=mock_context(),
            get_state=make_get_state(state),
        )

        json_str = '[{"tool_name": "test", "payload": {}}]'
        result = agent.post_process_response(json_str)
        assert result == json_str


class TestPostProcessResponseCallback:
    """Tests for post_process_response callback parameter."""

    def test_callback_returns_list_of_tool_calls(self) -> None:
        """Callback can return pre-parsed list of ToolCall dicts."""

        def wrap_response(response: str) -> PostProcessedResponse:
            return [{"tool_name": "wrapped", "payload": response}]

        state = mock_state([ToolMetadata("wrapped", "Wrapped tool", JSONSchema({}))])
        mock_client = MockLLMClient("raw text from LLM")
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
            post_process_response=wrap_response,
        )

        tool_calls = agent.step()

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "wrapped"
        assert tool_calls[0]["payload"] == "raw text from LLM"

    def test_callback_returns_transformed_string(self) -> None:
        """Callback can return a transformed string for JSON parsing."""

        def json_wrap(response: str) -> PostProcessedResponse:
            return json.dumps(
                [{"tool_name": "text_tool", "payload": {"text": response}}]
            )

        state = mock_state([ToolMetadata("text_tool", "Text tool", JSONSchema({}))])
        mock_client = MockLLMClient("hello world")
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
            post_process_response=json_wrap,
        )

        tool_calls = agent.step()

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "text_tool"
        assert tool_calls[0]["payload"] == {"text": "hello world"}

    def test_callback_with_multiple_tool_calls(self) -> None:
        """Callback can return multiple pre-parsed tool calls."""

        def multi_tool(response: str) -> PostProcessedResponse:
            return [
                {"tool_name": "log", "payload": {"message": f"Received: {response}"}},
                {"tool_name": "process", "payload": response},
            ]

        state = mock_state(
            [
                ToolMetadata("log", "Log tool", JSONSchema({})),
                ToolMetadata("process", "Process tool", JSONSchema({})),
            ]
        )
        mock_client = MockLLMClient("input data")
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
            post_process_response=multi_tool,
        )

        tool_calls = agent.step()

        assert len(tool_calls) == 2
        assert tool_calls[0]["tool_name"] == "log"
        assert tool_calls[0]["payload"] == {"message": "Received: input data"}
        assert tool_calls[1]["tool_name"] == "process"
        assert tool_calls[1]["payload"] == "input data"


class TestWrapAsToolCall:
    """Tests for wrap_as_tool_call helper function."""

    def test_wrap_as_tool_call_creates_transformer(self) -> None:
        """wrap_as_tool_call returns a callable transformer."""
        transformer = reponse_as_single_tool_call("my_tool")
        assert callable(transformer)

    def test_wrap_as_tool_call_wraps_response(self) -> None:
        """Transformer wraps response as single tool call."""
        transformer = reponse_as_single_tool_call("update_text")
        result = transformer("some text")

        assert len(result) == 1
        assert result[0]["tool_name"] == "update_text"
        assert result[0]["payload"] == "some text"

    def test_wrap_as_tool_call_preserves_response_exactly(self) -> None:
        """Transformer preserves the response string exactly."""
        transformer = reponse_as_single_tool_call("save")
        response_with_special_chars = "Hello\nWorld\twith 'quotes' and \"more\""
        result = transformer(response_with_special_chars)

        assert result[0]["payload"] == response_with_special_chars

    def test_wrap_as_tool_call_as_callback(self) -> None:
        """wrap_as_tool_call works as post_process_response callback."""
        state = mock_state([ToolMetadata("output", "Output tool", JSONSchema({}))])
        mock_client = MockLLMClient("LLM response text")
        agent = Agent(
            name="agent",
            llm_client=mock_client,
            context=mock_context(),
            get_state=make_get_state(state),
            post_process_response=reponse_as_single_tool_call("output"),
        )

        tool_calls = agent.step()

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "output"
        assert tool_calls[0]["payload"] == "LLM response text"

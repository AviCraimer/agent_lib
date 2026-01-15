"""Agent - runtime agent that validates and coordinates tool calls.

Agent instances live outside the Store (in AgentRuntime) to maintain security boundaries.
Agent state lives in Store._state.agent_state and is accessed through a state selector,
not stored on the Agent itself. This keeps the Store as the single source of truth.

The Agent validates messages and LLM responses but does not execute tools directly.
Tool execution is handled by AgentRuntime which has access to the actual handlers.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypedDict

import jsonschema

from agent_lib.store.state.AgentState import AgentState
from agent_lib.agent.LLMClient import LLMClient
from agent_lib.context.components.LLMContext import LLMContext


class ToolCall(TypedDict):
    """A single tool call from the LLM response."""

    tool_name: str
    payload: dict[str, Any]


class ToolCallResponse(TypedDict):
    """Expected JSON format from LLM for tool calls."""

    tool_calls: list[ToolCall]


TOOL_CALL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "payload": {"anyOf": [{"type": "object"}, {"type": "string"}]},
                },
                "required": ["tool_name"],
            },
        }
    },
    "required": ["tool_calls"],
}


class Agent:
    """Runtime agent that validates and coordinates tool calls.

    Agents are purely behavioral - they validate messages, call the LLM, and validate
    responses. Agent state (including tool metadata) lives in the Store and is accessed
    through a state selector. Tool execution is handled by AgentRuntime.

    The agent's step() method does one LLM call, parses the response for tool calls,
    validates them, and returns them for execution by AgentRuntime.

    This separation ensures that:
    - Agent never has direct access to tool handlers (security boundary)
    - Tool metadata is in state (accessible to system prompts via Store.connect)
    - AgentRuntime orchestrates execution
    """

    name: str
    llm_client: LLMClient
    context: LLMContext
    get_state: Callable[[], AgentState]

    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        context: LLMContext,
        get_state: Callable[[], AgentState],
    ) -> None:
        """Create an agent.

        Args:
            name: Unique identifier for this agent
            llm_client: The LLM client to use for generating responses
            context: The LLMContext for this agent (connected to store for dynamic rendering)
            get_state: Callable that returns the agent's current state from the store (read-only)
        """
        self.name = name
        self.llm_client = llm_client
        self.context = context
        self.get_state = get_state

    def has_tool(self, name: str) -> bool:
        """Check if the agent has a specific tool."""
        return any(t.name == name for t in self.get_state().tools)

    def list_tools(self) -> list[str]:
        """List the names of all tools granted to this agent."""
        return [t.name for t in self.get_state().tools]

    def _validate_messages(self, context: LLMContext) -> list[dict[str, str]]:
        """Render and validate the messages from context.

        Validates against the LLM client's message_json_schema.

        Args:
            context: The LLMContext containing the messages component

        Returns:
            The parsed messages list

        Raises:
            json.JSONDecodeError: If messages don't render to valid JSON
            jsonschema.ValidationError: If messages don't match the schema
        """
        messages_json = context.messages.render()

        try:
            messages = json.loads(messages_json)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Agent '{self.name}' messages component rendered invalid JSON: {e.msg}",
                e.doc,
                e.pos,
            )

        schema = json.loads(self.llm_client.message_json_schema)
        for msg in messages:
            jsonschema.validate(msg, schema)

        return messages  # type: ignore[return-value]

    def _validate_response(self, response: str) -> list[ToolCall]:
        """Parse and validate the LLM response.

        Validates:
        1. Response is valid JSON
        2. Response matches TOOL_CALL_RESPONSE_SCHEMA
        3. Each tool is granted to this agent
        4. Each tool payload matches the tool's json_schema

        Args:
            response: The raw LLM response string

        Returns:
            List of validated tool calls

        Raises:
            json.JSONDecodeError: If response is not valid JSON
            jsonschema.ValidationError: If response or payload doesn't match schema
            KeyError: If a tool is not granted to this agent
        """
        try:
            parsed: dict[str, Any] = json.loads(response)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Agent '{self.name}' received invalid JSON response: {e.msg}",
                e.doc,
                e.pos,
            )

        # Validate response structure
        jsonschema.validate(parsed, TOOL_CALL_RESPONSE_SCHEMA)

        tool_calls: list[ToolCall] = parsed["tool_calls"]

        # Get current tool metadata from state
        state = self.get_state()
        tools_by_name = {t.name: t for t in state.tools}

        # Validate each tool call
        for tool_call in tool_calls:
            tool_name = tool_call["tool_name"]

            # Check tool is granted
            if tool_name not in tools_by_name:
                raise KeyError(
                    f"Tool '{tool_name}' is not granted to agent '{self.name}'"
                )

            # Validate payload against tool's schema
            tool_metadata = tools_by_name[tool_name]
            if tool_metadata.json_schema:
                payload = tool_call.get("payload", {})
                schema = json.loads(tool_metadata.json_schema)
                jsonschema.validate(payload, schema)

        return tool_calls

    def step(self) -> list[ToolCall]:
        """Execute one step: validate messages → LLM call → validate response → return tool calls.

        Uses self.context which is connected to the store and renders dynamically.
        Returns the validated tool calls for AgentRuntime to execute.

        Returns:
            List of validated tool calls to be executed by AgentRuntime

        Raises:
            json.JSONDecodeError: If messages or LLM response is not valid JSON
            jsonschema.ValidationError: If messages, response, or payload doesn't match schema
            KeyError: If a tool call references a tool not granted to this agent
        """
        self._validate_messages(self.context)

        response = self.llm_client.get_response(self.context)
        tool_calls = self._validate_response(response)

        return tool_calls

"""Agent - runtime agent that validates and coordinates tool calls.

Agent instances live outside the Store (in AgentRuntime) to maintain security boundaries.
Agent state lives in Store._state.agent_state and is accessed through a state selector,
not stored on the Agent itself. This keeps the Store as the single source of truth.

The Agent validates messages and LLM responses but does not execute tools directly.
Tool execution is handled by AgentRuntime which has access to the actual handlers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict, cast

import jsonschema

from agent_lib.agent.LLMClient import LLMClient
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.store.state.AgentState import AgentState
from agent_lib.util.json_utils import json, JSONPyValue


class ToolCall(TypedDict):
    """A single tool call from the LLM response."""

    tool_name: str
    payload: JSONPyValue


type PostProcessedResponse = str | list[ToolCall]
"""Return type for post_process_response - either a string to parse or pre-parsed tool calls."""

type PostProcessResponseFn = Callable[[str], PostProcessedResponse]
"""Callback type for transforming LLM responses before validation."""


TOOL_CALLS_SCHEMA = json.load_schema(Path(__file__).parent / "tool_calls_schema.json")


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
        post_process_response: PostProcessResponseFn | None = None,
    ) -> None:
        """Create an agent.

        Args:
            name: Unique identifier for this agent
            llm_client: The LLM client to use for generating responses
            context: The LLMContext for this agent (connected to store for dynamic rendering)
            get_state: Callable that returns the agent's current state from the store (read-only)
            post_process_response: Optional callback to transform LLM response before validation. Use this to wrap raw text responses as tool calls without JSON round-trip.
        """
        self.name = name
        self.llm_client = llm_client
        self.context = context
        self.get_state = get_state
        if post_process_response is not None:
            self.post_process_response = post_process_response  # type: ignore[method-assign]

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
            messages_unvalidated = json.parse(messages_json)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Agent '{self.name}' messages component rendered invalid JSON: {e.msg}",
                e.doc,
                e.pos,
            )

        if not isinstance(messages_unvalidated, list):
            raise jsonschema.ValidationError("Messages must be a JSON array")

        for msg in messages_unvalidated:
            jsonschema.validate(msg, self.llm_client.message_json_schema)

        return cast(list[dict[str, str]], messages_unvalidated)

    def post_process_response(self, response: str) -> PostProcessedResponse:
        """Post-process LLM response before validation.

        Default implementation passes through unchanged. Provide a post_process_response callback at construction to transform raw text into tool calls.

        Args:
            response: The raw LLM response string

        Returns:
            Either the response string (possibly transformed) for JSON parsing, or a pre-parsed list of ToolCall dicts to skip the JSON parsing step.
        """
        return response

    def _validate_response(self, response: str) -> list[ToolCall]:
        """Parse and validate the LLM response.

        Validates:
        1. Calls post_process_response for optional transformation
        2. If result is a string, parses as JSON
        3. Response matches TOOL_CALL_RESPONSE_SCHEMA
        4. Each tool is granted to this agent
        5. Each tool payload matches the tool's json_schema

        Args:
            response: The raw LLM response string

        Returns:
            List of validated tool calls

        Raises:
            json.JSONDecodeError: If response is not valid JSON
            jsonschema.ValidationError: If response or payload doesn't match schema
            KeyError: If a tool is not granted to this agent
        """
        processed = self.post_process_response(response)

        # If post_process_response returned a list, use it directly
        if isinstance(processed, list):
            tool_calls_unvalidated = processed
        else:
            # Otherwise, parse the string as JSON
            try:
                tool_calls_unvalidated = json.parse(processed)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"Agent '{self.name}' received invalid JSON response: {e.msg}",
                    e.doc,
                    e.pos,
                ) from e

        # Validate response structure (array of tool calls)
        jsonschema.validate(tool_calls_unvalidated, TOOL_CALLS_SCHEMA)
        tool_calls = cast(list[ToolCall], tool_calls_unvalidated)

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
            payload = tool_call.get("payload", {})
            jsonschema.validate(payload, tool_metadata.payload_json_schema)

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

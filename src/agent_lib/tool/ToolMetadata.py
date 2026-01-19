"""ToolMetadata - tool information visible to agents.

ToolMetadata contains only the metadata about a tool (name, description, schema)
without the handler. This lives in AgentState so it can be accessed by system prompts.
The actual handler lives in AgentRuntime.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_lib.util.json_utils import JSONSchema


@dataclass(frozen=True)
class ToolMetadata:
    """Tool metadata visible to agents (no handler).

    Attributes:
        name: Unique identifier for this tool
        description: Human-readable description (useful for LLM tool selection)
        json_schema: JSON schema describing the payload format
    """

    name: str
    description: str
    payload_json_schema: JSONSchema

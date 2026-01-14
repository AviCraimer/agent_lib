"""Tool - a capability that can be granted to an agent.

Tools are the agent's sandboxed interface. They may wrap Store actions internally,
but the agent never sees the Store directly. Some tools don't involve actions at all
(external APIs, spawning agents, etc.).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agent_lib.agent.ToolMetadata import ToolMetadata


@dataclass
class Tool[P, R]:
    """A capability that can be granted to an agent.

    Tools provide a sandboxed interface - the agent invokes the tool with a payload
    and receives a result, but never has direct access to the Store or other internals.

    Type Parameters:
        P: Payload type the tool accepts
        R: Result type the tool returns

    Attributes:
        name: Unique identifier for this tool
        description: Human-readable description (useful for LLM tool selection)
        json_schema: JSON schema string describing the payload format
        handler: The function that executes when the tool is invoked
    """

    name: str
    description: str
    json_schema: str
    handler: Callable[[P], R]

    def __call__(self, payload: P) -> R:
        """Invoke the tool with the given payload."""
        return self.handler(payload)

    def to_metadata(self) -> ToolMetadata:
        """Extract tool metadata (without handler) for storage in agent state."""
        return ToolMetadata(
            name=self.name,
            description=self.description,
            json_schema=self.json_schema,
        )

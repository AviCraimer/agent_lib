"""Protocol for LLM clients.

Any LLM client that implements get_response(LLMContext) -> str can be used with Agent.
This allows swapping between different LLM providers (Anthropic, OpenAI, etc.)
"""

from __future__ import annotations

from typing import Protocol

from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.util.json_utils import JSONSchema


class LLMClient(Protocol):
    """Protocol for LLM clients.

    Any class with a get_response method matching this signature satisfies the protocol.

    Attributes:
        message_json_schema: JSON schema defining the expected format for the message object. Used by Agent to validate the rendered messages from LLMContext.messages.
    """

    message_json_schema: JSONSchema

    def get_response(self, context: LLMContext) -> str:
        """Get a response from the LLM.

        Args:
            context: The LLMContext containing system prompt and messages

        Returns:
            The LLM's response as a string
        """
        ...

"""LLMContext - context structure for LLM calls.

LLMContext holds the system prompt and messages components for an LLM call.
Both are CtxComponents that render dynamically, allowing messages to reflect
current state when rendered.
"""

from dataclasses import dataclass

from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps


@dataclass
class LLMContext:
    """Context for an LLM call.

    Attributes:
        system_prompt: Component that renders to the system prompt string
        messages: Component that renders to JSON array of message objects.

        The JSON schema for message objects is defined by the LLMClient.message_json_schema.
    """

    system_prompt: CtxComponent[NoProps]
    messages: CtxComponent[NoProps]

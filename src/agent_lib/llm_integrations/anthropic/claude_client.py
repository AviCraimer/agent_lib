from __future__ import annotations

import json
from typing import Any, Literal, Unpack

import anthropic
from anthropic.types import ContentBlock, MessageParam, TextBlock
from anthropic.types.message_create_params import MessageCreateParamsBase

from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.environment import anthropic_api_key

CLAUDE_MODELS = {
    "sonnet": "claude-sonnet-4-5",
    "haiku": "claude-haiku-4-5",
    "opus": "claude-opus-4-5",
}

type ModelSize = Literal["sonnet", "haiku", "opus"]

# JSON schema for a single Claude message object
CLAUDE_MESSAGE_SCHEMA = """{
    "type": "object",
    "properties": {
        "role": {"type": "string", "enum": ["user", "assistant"]},
        "content": {"type": "string"}
    },
    "required": ["role", "content"]
}"""


class ClaudeClient:
    """Claude LLM client that implements the LLMClient protocol."""

    config: MessageCreateParamsBase
    message_json_schema: str = CLAUDE_MESSAGE_SCHEMA

    def __init__(self, model: ModelSize = "haiku", api_key: str = anthropic_api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.config = {
            "max_tokens": 1024,
            "temperature": 0.7,
            "model": CLAUDE_MODELS[model],
            "messages": [],
        }

    def set_model(self, model: ModelSize) -> None:
        self.config["model"] = CLAUDE_MODELS[model]

    def set_config(self, **kwargs: Unpack[MessageCreateParamsBase]) -> None:
        """Update the config with the provided kwargs.

        Args:
            **kwargs: Any valid MessageCreateParamsBase fields (max_tokens, temperature, top_p, top_k, stop_sequences, etc.)
        """
        self.config.update(kwargs)

    @staticmethod
    def _parse_messages(messages_json: str) -> list[MessageParam]:
        """Parse JSON messages and convert to Anthropic MessageParam format.

        Args:
            messages_json: JSON string of messages array

        Returns:
            List of MessageParam for Anthropic API
        """
        messages: list[dict[str, Any]] = json.loads(messages_json)

        claude_messages: list[MessageParam] = [
            {
                "content": msg["content"],
                "role": "assistant" if msg.get("role") == "assistant" else "user",
            }
            for msg in messages
            if msg.get("role") in ["user", "assistant"]
        ]

        return claude_messages

    def get_response(self, context: LLMContext) -> str:
        """Get a response from Claude.

        Args:
            context: The LLMContext containing system prompt and messages components

        Returns:
            The model's response text
        """
        system_prompt = context.system_prompt.render()
        messages_json = context.messages.render()

        try:
            cleaned_messages = self._parse_messages(messages_json)

            # Claude API requires at least one message
            if not cleaned_messages:
                cleaned_messages: list[MessageParam] = [
                    {"role": "user", "content": "Please follow the system prompt."}
                ]

            params: MessageCreateParamsBase = {
                **self.config,
                "system": system_prompt,
                "messages": cleaned_messages,
            }

            content: ContentBlock = self.client.messages.create(**params).content[0]

            assert isinstance(content, TextBlock)
            return content.text
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")


if __name__ == "__main__":
    from agent_lib.context.CtxComponent import CtxComponent

    client = ClaudeClient()
    ctx = LLMContext(
        system_prompt=CtxComponent.leaf(lambda: ""),
        messages=CtxComponent.leaf(
            lambda: '[{"role": "user", "content": "Tell me a short joke"}]'
        ),
    )
    joke = client.get_response(ctx)
    print(joke)

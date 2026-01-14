from __future__ import annotations

from typing import Literal, TypedDict, Unpack
import anthropic
from anthropic.types import MessageParam, TextBlock, ContentBlock

from anthropic.types.message_create_params import MessageCreateParamsBase


from agent_lib.context.components.LLMContext import (
    LLMContext,
    UserRoleMsgCtx,
    AgentRoleMsgCtx,
    ChatMsgCtx,
)
from agent_lib.environment import anthropic_api_key

CLAUDE_MODELS = {
    "sonnet": "claude-sonnet-4-5",
    "haiku": "claude-haiku-4-5",
    "opus": "claude-opus-4-5",
}

type ModelSize = Literal["sonnet", "haiku", "opus"]


class ClaudeChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


# Core Claude interaction
class ClaudeClient:
    config: MessageCreateParamsBase

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
    def clean_messages_(history: list[ClaudeChatMessage]) -> list[MessageParam]:
        """
        Ensures only user and assistant messages are in message list.
        """

        claude_messages: list[MessageParam] = [
            {
                "content": msg["content"],
                "role": "assistant" if msg.get("role") == "assistant" else "user",
            }
            for msg in history
            if msg["role"] in ["user", "assistant"]
        ]

        return claude_messages

    @staticmethod
    def _chat_msg_to_role(msg: ChatMsgCtx) -> Literal["user", "assistant"]:
        """Determine the role based on the message type."""
        match msg:
            case UserRoleMsgCtx():
                return "user"
            case AgentRoleMsgCtx():
                return "assistant"

    @staticmethod
    def from_llm_context(ctx: LLMContext) -> tuple[str, list[ClaudeChatMessage]]:
        """Convert an LLMContext to Anthropic API parameters.

        Args:
            ctx: The LLMContext to convert

        Returns:
            A tuple of (system_prompt, messages) ready for get_response()
        """
        messages: list[ClaudeChatMessage] = [
            {
                "role": ClaudeClient._chat_msg_to_role(msg),
                "content": msg.render(),
            }
            for msg in ctx.messages
        ]
        system_prompt = ctx.system_prompt.render()

        return (
            system_prompt,
            messages,
        )

    def get_response(self, context: LLMContext) -> str:
        """Get a response from Claude.

        Args:
            context: The LLMContext containing system prompt and messages

        Returns:
            The model's response text
        """
        system_prompt, msgs = self.from_llm_context(context)

        try:
            cleaned_messages = ClaudeClient.clean_messages_(msgs)

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
        messages=[UserRoleMsgCtx(CtxComponent.leaf(lambda: "Tell me a short joke"))],
        system_prompt=CtxComponent.leaf(lambda: ""),
    )
    joke = client.get_response(ctx)
    print(joke)

from typing import Literal, TypedDict
import anthropic
from anthropic.types import MessageParam, TextBlock, ContentBlock

from agent_lib.environment import anthropic_api_key

CLAUDE_MODELS = {
    "sonnet": "claude-sonnet-4-5-latest",
    "haiku": "claude-haiku-4-5-latest",
    "opus": "claude-opus-4-5-latest",
}

type ModelSize = Literal["sonnet", "haiku", "opus"]


class ChatMessage(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str


# Core Claude interaction
class ClaudeClient:
    def __init__(self, api_key: str, model: ModelSize = "haiku"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_name = CLAUDE_MODELS[model]

    @classmethod
    def clean_messages_(cls, history: list[ChatMessage]) -> list[MessageParam]:
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

    def get_response(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.95,
    ) -> str:

        try:

            cleaned_messages = self.__class__.clean_messages_(messages)

            content: ContentBlock = self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                system=system_prompt,
                messages=cleaned_messages,
            ).content[0]

            assert isinstance(content, TextBlock)
            return content.text
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")


claude_client = ClaudeClient(api_key=anthropic_api_key)


if __name__ == "__main__":
    joke = claude_client.get_response(
        [{"role": "user", "content": "Tell me a short joke"}], ""
    )
    print(joke)

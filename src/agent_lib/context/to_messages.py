import enum
from typing import Literal
from agent_lib.context.CxtComponent import CtxComponent
from agent_lib.context.Props import NoProps
from agent_lib.llm_integrations.anthropic.claude_client import ChatMessage


def to_messages(msgComps: list[CtxComponent[NoProps] | str]) -> list[ChatMessage]:
    # Assumes user message is first and messages alternate
    return [
        {
            "role": (
                "user" if i % 2 == 0 else "assistant"
            ),  # "user" msgs are even indexed (starting from 0)
            "content": c if isinstance(c, str) else c.render(),
        }
        for i, c in enumerate(msgComps)
    ]

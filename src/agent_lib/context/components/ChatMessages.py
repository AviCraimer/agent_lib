"""ChatMessages - pre-built component for rendering agent message history.

This component renders an agent's history to JSON format suitable for LLM calls.
Connect it to a Store using Store.connect with a selector that provides the history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import Props


@dataclass(frozen=True)
class ChatMessagesProps(Props):
    """Props for ChatMessages component.

    Attributes:
        history: List of message dicts with 'role' and 'content' keys
    """

    history: list[dict[str, str]]


def _render_chat_messages(props: ChatMessagesProps) -> str:
    """Render message history to JSON array.

    Args:
        props: Contains the history to render

    Returns:
        JSON string of the messages array
    """
    return json.dumps(props.history)


ChatMessages: CtxComponent[ChatMessagesProps] = CtxComponent(
    _render_chat_messages, ChatMessagesProps
)
"""Pre-built component for rendering chat message history.

Usage with Store.connect:
    messages_component = store.connect(
        ChatMessages,
        lambda s: ChatMessagesProps(history=s._state.agent_state["agent_name"].history)
    )

This creates a NoProps component that dynamically renders the current history.
"""

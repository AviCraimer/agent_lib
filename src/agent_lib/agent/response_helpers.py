"""Helper functions for common post_process_response patterns."""

from __future__ import annotations

from collections.abc import Callable

from agent_lib.agent.Agent import PostProcessResponseFn, ToolCall


def reponse_as_single_tool_call(tool_name: str) -> PostProcessResponseFn:
    """Returns a function that wraps raw text as a single tool call.

    Useful for creating post_process_response implementations:
        post_process_response = wrap_as_tool_call("update_text")

    Args:
        tool_name: The name of the tool to wrap the response as

    Returns:
        A function that takes a response string and returns a list with a single ToolCall
    """

    def post_process_fn(response: str) -> list[ToolCall]:
        return [{"tool_name": tool_name, "payload": response}]

    return post_process_fn

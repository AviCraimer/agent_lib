from dataclasses import dataclass
import json
from agent_lib.agent.Agent import ToolCall
from agent_lib.agent.LLMClient import LLMClient
from agent_lib.context.CtxComponent import (
    CtxComponent,
    PromptTag,
    SystemTag,
    Tag,
    TagProps,
)

from agent_lib.context.Props import Props, propsclass
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.examples.exact_text_length.store import ExactLengthStore
from agent_lib.llm_integrations.anthropic.claude_client import ClaudeClient


@propsclass
class WriterProps(Props):
    user_prompt: str
    target_wordcount: int
    prev_generated_text: str | None
    current_wordcount: int | None


PreviousTextTag = Tag().preset(TagProps(tag="previous-text", line_breaks=True))


def render_fn(props: WriterProps):

    instruction = f"""Your goal is to write text based on the following prompt:\n\n{PromptTag(props.user_prompt)}\n\n. The generated text should have exactly {props.target_wordcount} words. No other text should be generated."""

    if props.prev_generated_text and props.current_wordcount:
        instruction += f"""\n\n You have previously attempted this task and you generated the following text:{PreviousTextTag(props.prev_generated_text)}This has a word count of {props.current_wordcount}"""

    return SystemTag(instruction).render()


WriterComponent = CtxComponent(render_fn, WriterProps)


class WriterLlmClient(LLMClient):
    claude_client = ClaudeClient("opus")
    message_json_schema = claude_client.message_json_schema

    def get_response(self, context: LLMContext):
        text = self.claude_client.get_response(context)

        call = {"tool_calls": [{"tool_name": "update_text", "payload": text}]}

        return json.dumps(call)


def map_store_to_writer(store: ExactLengthStore) -> WriterProps:
    return WriterProps(
        user_prompt=store.state.user_prompt,
        target_wordcount=store.state.target_wordcount,
        prev_generated_text=store.state.current_text,
        current_wordcount=store.state.wordcount,
    )

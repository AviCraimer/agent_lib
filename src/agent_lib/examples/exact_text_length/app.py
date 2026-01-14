from agent_lib.agent.AgentRuntime import AgentRuntime
from agent_lib.examples.exact_text_length.store import ExactLengthStore
from agent_lib.examples.exact_text_length.writer_agent import (
    WriterComponent,
    map_store_to_writer,
)
from agent_lib.llm_integrations.anthropic.claude_client import ClaudeClient


class ExactLengthApp(AgentRuntime):

    def __init__(self, user_prompt: str, target_wordcount: int):
        store = ExactLengthStore(user_prompt, target_wordcount)
        super().__init__(store)

        WriterContext = store.connect(WriterComponent, map_store_to_writer)

        self.create_agent(name="writer", llm_client=ClaudeClient(), system_prompt=WriterContext)


exact_length = ExactLengthApp(
    "Write three paragraphs on the question of how we could know if AI systems are conscious.",
    400,
)

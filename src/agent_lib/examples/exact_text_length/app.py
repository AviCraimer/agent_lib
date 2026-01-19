from agent_lib.agent.response_helpers import reponse_as_single_tool_call
from agent_lib.agent_app.AgentRuntime import AgentRuntime
from agent_lib.examples.exact_text_length.store import ExactLengthStore
from agent_lib.examples.exact_text_length.writer_context import (
    WriterComponent,
    map_store_to_writer,
)
from agent_lib.llm_integrations.anthropic.claude_client import ClaudeClient


class ExactLengthApp(AgentRuntime[ExactLengthStore]):

    def __init__(self, user_prompt: str, target_wordcount: int):
        store = ExactLengthStore(user_prompt, target_wordcount)
        self._store: ExactLengthStore = store
        super().__init__(store)

        WriterContext = store.connect(WriterComponent, map_store_to_writer)

        self.create_agent(
            name="writer",
            llm_client=ClaudeClient("opus"),
            system_prompt=WriterContext,
            post_process_response=reponse_as_single_tool_call("update_text"),
        )
        update_text = self.action_to_tool("update_text", "update_text")

        self.grant_tool("writer", update_text)
        # Set the writer to act initially.
        store.update_should_act({"agent_name": "writer", "should_act": True})

    def run(self):
        count = 1

        while not self._store.state.finished and count <= 10:
            state = self._store.state
            text = state.current_text
            wordcount = state.wordcount
            target = state.target_wordcount
            if text:
                print(
                    f"Attempt {count} with {wordcount} vs target wordcount of {target}:"
                )
                # print(text)
            self.run_once()

            count = count + 1

        if self._store.state.finished:
            print("Success")
            print(f"Text with Exact Wordcount of {self._store.state.wordcount}:\n")
            print(self._store.state.current_text)
        else:
            print(f"Terminated after {count} attempts")


if __name__ == "__main__":
    exact_length = ExactLengthApp(
        "Write three paragraphs on the question of how we could know if AI systems are conscious.",
        400,
    )

    exact_length.run()

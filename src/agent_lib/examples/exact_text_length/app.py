from agent_lib.agent_app.AgentRuntime import AgentRuntime
from agent_lib.examples.exact_text_length.store import ExactLengthStore
from agent_lib.examples.exact_text_length.writer_agent import (
    WriterComponent,
    map_store_to_writer,
    WriterLlmClient,
)


class ExactLengthApp(AgentRuntime):

    def __init__(self, user_prompt: str, target_wordcount: int):
        store = ExactLengthStore(user_prompt, target_wordcount)
        self._store: ExactLengthStore = store
        super().__init__(store)

        WriterContext = store.connect(WriterComponent, map_store_to_writer)

        self.create_agent(
            name="writer", llm_client=WriterLlmClient(), system_prompt=WriterContext
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


exact_length = ExactLengthApp(
    "Write three paragraphs on the question of how we could know if AI systems are conscious.",
    400,
)

exact_length.run()

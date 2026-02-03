"""Example app demonstrating exact text length writing.

This example shows how to use AgentApp and StoreUpdater to create an agent
that writes text to hit an exact word count.
"""

# pyright: reportPrivateUsage=false
# App needs access to Store internals (_state) for state mutations in updaters.

from collections.abc import Callable

from agent_lib.agent.response_helpers import reponse_as_single_tool_call
from agent_lib.agent_app.AgentApp import AgentApp
from agent_lib.examples.exact_text_length.state import (
    ExactLengthState,
    update_text,
    update_wordcount,
    update_finished,
)
from agent_lib.examples.exact_text_length.writer_context import (
    WriterComponent,
    map_to_writer,
)
from agent_lib.llm_integrations.anthropic.claude_client import ClaudeClient
from agent_lib.store.Store import Store
from agent_lib.store.updaters.update_should_act import (
    UpdateShouldActPayload,
    update_should_act,
)


class ExactLengthApp(AgentApp[ExactLengthState]):

    def __init__(self, user_prompt: str, target_wordcount: int):

        state = ExactLengthState()
        state.user_prompt = user_prompt
        state.target_wordcount = target_wordcount
        store = Store(state)
        super().__init__("Exact_Text_Writing_App", store)

        # Bind StoreUpdaters to this app
        self.update_text = update_text.bind(self)
        self.update_wordcount = update_wordcount.bind(self)
        self.update_finished = update_finished.bind(self)
        self.update_should_act = update_should_act.bind(self)

        # Subscribe to trigger wordcount update when text changes
        self.subscribers.append(self._on_text_change)

        WriterContext = store.connect(WriterComponent, map_to_writer)

        self.create_agent(
            name="writer",
            llm_client=ClaudeClient("haiku"),
            system_prompt=WriterContext,
            post_process_response=reponse_as_single_tool_call("update_text"),
        )

        # Grant the update_text tool to the writer agent
        self.grant_tool("writer", self.update_text)

        # Set the writer to act initially
        self.update_should_act(
            UpdateShouldActPayload(agent_name="writer", should_act=True)
        )

    def _on_text_change(self, affects: Callable[[str], bool]) -> None:
        """Handle text changes by updating wordcount and checking completion."""
        if affects("current_text"):
            self.update_wordcount(None)

        state: ExactLengthState = self._store._state
        if state.wordcount == state.target_wordcount:
            self.update_finished(True)

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
        "Write on the question of how we could know if AI systems are conscious.",
        100,
    )

    exact_length.run()

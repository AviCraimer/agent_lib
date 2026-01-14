from agent_lib.agent.AgentRuntime import AgentRuntime
from agent_lib.examples.exact_text_length.store import ExactLengthStore

store = ExactLengthStore()


class ExactLengthApp(AgentRuntime):

    def __init__(self, user_prompt: str, target_wordcount: int):
        super().__init__(store)


exact_length = ExactLengthApp()

# exact_length.create_agent()

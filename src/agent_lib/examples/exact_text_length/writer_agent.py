from agent_lib.context.CtxComponent import CtxComponent

# TODO: Move this and other reusable components to context/components
from agent_lib.examples.transcription import SystemPrompt


"""Your goal is to write text with a specified number of words. """


WriterIntro = CtxComponent.leaf(lambda: """Your goal is to write a """)

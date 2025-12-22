from agent_lib.component.ContextComponent import (
    Children,
    ContextComponent,
    RenderFn,
    Tag,
)


# Props types
class TranscriptionProps:
    def __init__(
        self, audio_format: str, language: str, children: Children = None
    ):
        self.audio_format = audio_format
        self.language = language
        self.children = children


# Render functions

system_prompt: RenderFn = (
    lambda comp, children, props: f"You are a transcription assistant.\n{comp>>children}"
)

instructions: RenderFn[TranscriptionProps] = (
    lambda comp, children, props: f"""Transcribe the following {props.audio_format} audio in {props.language}.
Guidelines:
{comp>>children}"""
)

transcript_output: RenderFn[None] = lambda comp, children, props: "Provide the transcript below:"


# Components
SystemPrompt = ContextComponent(system_prompt, Tag("system", line_breaks=True))
Instructions = ContextComponent(
    instructions,
    Tag("instructions", line_breaks=True),
    list_delimitor=("", "\n"),
)
TranscriptOutput = ContextComponent(transcript_output, None)


# Usage
def build_transcription_prompt() -> str:
    prompt = SystemPrompt(
        [
            Instructions[
                TranscriptionProps(
                    audio_format="mp3",
                    language="English",
                    children=[
                        "- Include timestamps every 30 seconds",
                        "- Mark speaker changes with [Speaker 1], [Speaker 2], etc.",
                        "- Note any unclear audio as [inaudible]",
                    ],
                )
            ],
            TranscriptOutput,
        ],
        None,
    )

    return prompt


if __name__ == "__main__":
    result = build_transcription_prompt()
    print(result)

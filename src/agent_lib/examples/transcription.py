from agent_lib.component.CxtComponent import (
    Children,
    CtxComponent,
    Tag,
)


TranscriptCTA = CtxComponent.leaf(lambda: "Provide the transcript below:", ("\n", ""))

SystemPrompt = CtxComponent.wrapper(Tag("system", line_breaks=True))

TranscriptionAssistantRole = CtxComponent.leaf(
    lambda: f"You are a transcription assistant.",
    Tag("your-role", line_breaks=False),
)


class AudioProps:
    def __init__(self, audio_format: str, language: str, children: Children = None):
        self.audio_format = audio_format
        self.language = language
        self.children = children


AudioInstructions = CtxComponent[AudioProps](
    lambda props, children: f"""Transcribe the following {props.audio_format} audio in {props.language}.
Guidelines:
{children}""",
    Tag("instructions", line_breaks=True),
    list_delimitor=("", "\n"),
)


# Usage

TranscriptionSystemPrompt = SystemPrompt(
    {
        "children": [
            TranscriptionAssistantRole,
            AudioInstructions(
                AudioProps(
                    audio_format="mp3",
                    language="English",
                    children=[
                        "- Include timestamps every 30 seconds",
                        "- Mark speaker changes with [Speaker 1], [Speaker 2], etc.",
                        "- Note any unclear audio as [inaudible]",
                    ],
                )
            ),
            TranscriptCTA,
        ]
    }
)


TranscriptionSystemPrompt = SystemPrompt(
    {
        "children": [
            TranscriptionAssistantRole,
            AudioInstructions(
                AudioProps(
                    audio_format="mp3",
                    language="English",
                    children=[
                        "- Include timestamps every 30 seconds",
                        "- Mark speaker changes with [Speaker 1], [Speaker 2], etc.",
                        "- Note any unclear audio as [inaudible]",
                    ],
                )
            ),
            TranscriptCTA,
        ]
    }
)


if __name__ == "__main__":
    result = TranscriptionSystemPrompt.render()
    print(result)

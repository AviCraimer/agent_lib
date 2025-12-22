from agent_lib.component.ContextComponent import (
    Children,
    ContextComponent,
    JustChildren,
    Tag,
)


# Props types
class TranscriptionProps:
    def __init__(self, audio_format: str, language: str, children: Children = None):
        self.audio_format = audio_format
        self.language = language
        self.children = children


SystemPrompt = ContextComponent[JustChildren](
    lambda comp, props: f"You are a transcription assistant.\n{comp>>props["children"]}",
    Tag("system", line_breaks=True),
)

Instructions = ContextComponent[TranscriptionProps](
    lambda comp, props: f"""Transcribe the following {props.audio_format} audio in {props.language}.
Guidelines:
{comp>>props.children}""",
    Tag("instructions", line_breaks=True),
    list_delimitor=("", "\n"),
)

TranscriptOutput = ContextComponent[None](
    lambda comp, props: "Provide the transcript below:"
)


# Usage
def build_transcription_prompt() -> str:
    prompt = SystemPrompt.render(
        {
            "children": [
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
                TranscriptOutput[None],
            ]
        }
    )

    return prompt


if __name__ == "__main__":
    result = build_transcription_prompt()
    print(result)

from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.components.Tag import Tag, TagProps, SystemTag
from agent_lib.context.Props import Props


TranscriptCTA = CtxComponent.leaf(
    lambda: "Provide the transcript below:", "TranscriptCTA"
)


TranscriptionAssistantRole = (
    Tag()
    .preset(TagProps(tag="your-role", line_breaks=False))
    .pass_props("You are a transcription assistant.")
)


class AudioProps(Props):
    audio_format: str
    language: str


AudioInstructions = CtxComponent[AudioProps](
    lambda props: f"""Transcribe the following {props.audio_format} audio in {props.language}.
Guidelines:
{CtxComponent.render_children(props.children, "")}""",
    AudioProps,
)


# Usage

TranscriptionSystemPrompt = SystemTag(
    [
        TranscriptionAssistantRole,
        AudioInstructions.pass_props(
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
)


if __name__ == "__main__":
    from agent_lib.context.Props import NoProps

    result = TranscriptionSystemPrompt.render(NoProps())
    print(result)

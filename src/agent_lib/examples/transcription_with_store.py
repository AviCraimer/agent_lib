from __future__ import annotations
from agent_lib.context.Props import NoProps
from agent_lib.examples.transcription import (
    AudioInstructions,
    AudioProps,
    SystemPrompt,
    TranscriptCTA,
    TranscriptionAssistantRole,
)
from agent_lib.store.Action import Action
from agent_lib.store.Store import Store


# Store (state is now part of the store itself)


class TranscriptionStore(Store):
    audio_format: str
    language: str

    def __init__(self, audio_format: str, language: str):
        super().__init__()
        self.audio_format = audio_format
        self.language = language

    @Store.action
    def set_language(self, lang: str) -> frozenset[str]:
        if self.language == lang:
            return Action.scope.no_op
        self.language = lang
        return frozenset({"language"})

    @Store.action
    def set_format(self, fmt: str) -> frozenset[str]:
        if self.audio_format == fmt:
            return Action.scope.no_op
        self.audio_format = fmt
        return frozenset({"audio_format"})


# Usage

store = TranscriptionStore(audio_format="mp3", language="English")

# Connect component to store
BoundAudioInstructions = store.connect(
    AudioInstructions,
    lambda s: AudioProps(
        audio_format=s.audio_format,
        language=s.language,
        children=[
            "- Include timestamps every 30 seconds",
            "- Mark speaker changes with [Speaker 1], [Speaker 2], etc.",
            "- Note any unclear audio as [inaudible]",
        ],
    ),
)

TranscriptionSystemPrompt = SystemPrompt(
    [
        TranscriptionAssistantRole,
        BoundAudioInstructions,
        TranscriptCTA,
    ]
)


if __name__ == "__main__":
    print("=== Initial render (English, mp3) ===")
    print(TranscriptionSystemPrompt.render(NoProps()))

    print("\n=== After changing language to Spanish ===")
    store.set_language("Spanish")  # Access via descriptor - auto-bound!
    print(TranscriptionSystemPrompt.render(NoProps()))

    print("\n=== After changing format to wav ===")
    store.set_format("wav")  # Access via descriptor - auto-bound!
    print(TranscriptionSystemPrompt.render(NoProps()))

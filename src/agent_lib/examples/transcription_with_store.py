"""Example demonstrating Store with component connection.

This example shows how to use Store.connect() to bind components to state.
Since there's no AgentApp or agent involvement, state mutations are done
via simple methods rather than StoreUpdaters.
"""

from __future__ import annotations

from agent_lib.context.Props import NoProps
from agent_lib.examples.transcription import (
    AudioInstructions,
    AudioProps,
    SystemPrompt,
    TranscriptCTA,
    TranscriptionAssistantRole,
)
from agent_lib.store.Store import Store


class TranscriptionStore(Store):
    """Store for transcription settings.

    This store manages transcription configuration (format, language).
    Since there's no agent involved, state mutations are simple methods.
    """

    audio_format: str
    language: str

    def __init__(self, audio_format: str, language: str):
        super().__init__()
        self.audio_format = audio_format
        self.language = language

    def set_language(self, lang: str) -> None:
        """Set the transcription language."""
        self.language = lang

    def set_format(self, fmt: str) -> None:
        """Set the audio format."""
        self.audio_format = fmt


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
    store.set_language("Spanish")
    print(TranscriptionSystemPrompt.render(NoProps()))

    print("\n=== After changing format to wav ===")
    store.set_format("wav")
    print(TranscriptionSystemPrompt.render(NoProps()))

from dataclasses import dataclass

from agent_lib.component.Store import Store
from agent_lib.examples.demo_1.transcription import (
    AudioInstructions,
    AudioProps,
    SystemPrompt,
    TranscriptCTA,
    TranscriptionAssistantRole,
)


# State

@dataclass
class AppState:
    audio_format: str
    language: str


# Store with actions

class TranscriptionStore(Store[AppState]):
    def set_language(self, language: str) -> None:
        self._state.language = language

    def set_format(self, fmt: str) -> None:
        if fmt in ["mp3", "wav", "flac"]:
            self._state.audio_format = fmt
        else:
            raise ValueError(f"Unsupported format: {fmt}")


# Usage

store = TranscriptionStore(AppState(audio_format="mp3", language="English"))

BoundAudioInstructions = store.connect(
    AudioInstructions,
    lambda state: AudioProps(
        audio_format=state.audio_format,
        language=state.language,
        children=[
            "- Include timestamps every 30 seconds",
            "- Mark speaker changes with [Speaker 1], [Speaker 2], etc.",
            "- Note any unclear audio as [inaudible]",
        ],
    ),
)

TranscriptionSystemPrompt = SystemPrompt(
    {
        "children": [
            TranscriptionAssistantRole,
            BoundAudioInstructions,
            TranscriptCTA,
        ]
    }
)


if __name__ == "__main__":
    print("=== Initial render (English, mp3) ===")
    print(TranscriptionSystemPrompt.render())

    print("\n=== After changing language to Spanish ===")
    store.set_language("Spanish")
    print(TranscriptionSystemPrompt.render())

    print("\n=== After changing format to wav ===")
    store.set_format("wav")
    print(TranscriptionSystemPrompt.render())

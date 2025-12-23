from dataclasses import dataclass

from agent_lib.store.Store import Store
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


class TranscriptionStore(Store[AppState]):
    @Store.action
    @staticmethod
    def set_language(state: AppState, lang: str) -> AppState:
        state.language = lang
        return state

    @Store.action
    @staticmethod
    def set_format(state: AppState, fmt: str) -> AppState:
        state.audio_format = fmt
        return state


# Usage

store = TranscriptionStore(AppState(audio_format="mp3", language="English"))

# Connect component to store
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
    store.set_language("Spanish")  # Access via descriptor - auto-bound!
    print(TranscriptionSystemPrompt.render())

    print("\n=== After changing format to wav ===")
    store.set_format("wav")  # Access via descriptor - auto-bound!
    print(TranscriptionSystemPrompt.render())

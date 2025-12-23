from dataclasses import dataclass

from agent_lib.store.Store import Action, Store
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


# Actions (defined independently of any store)


def _set_language(state: AppState, language: str) -> AppState:
    state.language = language
    return state


def _set_format(state: AppState, fmt: str) -> AppState:
    if fmt not in ["mp3", "wav", "flac"]:
        raise ValueError(f"Unsupported format: {fmt}")
    state.audio_format = fmt
    return state


# Usage
store = Store(AppState(audio_format="mp3", language="English"))

# Connect actions to store
set_language = store.connect(Action[str, AppState](_set_language))
set_format = store.connect(Action[str, AppState](_set_format))

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
    set_language("Spanish")
    print(TranscriptionSystemPrompt.render())

    print("\n=== After changing format to wav ===")
    set_format("wav")
    print(TranscriptionSystemPrompt.render())

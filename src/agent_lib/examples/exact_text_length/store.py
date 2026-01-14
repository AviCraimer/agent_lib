from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

from agent_lib.store.State import State
from agent_lib.store.Store import Store


@dataclass
class ExactLengthState(State):
    user_prompt: str = ""
    target_wordcount: int = 0
    current_text: str = ""
    wordcount: int = 0


def get_wordcount(text: str) -> int:
    return len(text.split(" "))


class ExactLengthStore(Store[ExactLengthState]):
    _state: ExactLengthState

    def __init__(self, user_prompt: str, target_wordcount: int) -> None:
        self._state = ExactLengthState(
            user_prompt=user_prompt,
            target_wordcount=target_wordcount,
        )
        super().__init__()

        # Subscribe to trigger update_wordcount when current_text changes
        self.subscribe(self._on_text_change)

    def _on_text_change(self, affects: Callable[[str], bool]) -> None:
        if affects("current_text"):
            self.update_wordcount(None)

    @Store.action
    def update_text(self: Self, new_text: str) -> frozenset[str]:
        self._state.current_text = new_text
        return frozenset({"_state.current_text"})

    @Store.action
    def update_wordcount(self: Self, payload: None = None) -> frozenset[str]:
        text = self._state.current_text

        self._state.wordcount = get_wordcount(text)
        return frozenset({"_state.wordcount"})

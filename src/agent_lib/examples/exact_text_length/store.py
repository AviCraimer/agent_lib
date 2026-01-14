from collections.abc import Callable
from dataclasses import dataclass
from typing import Self

from agent_lib.store.State import State
from agent_lib.store.Store import Store


class ExactLengthState(State):
    current_text: str
    wordcount: int
    target_wordcount: int
    user_prompt: str


class ExactLengthStore(Store[ExactLengthState]):
    _state: ExactLengthState

    def __init__(self, user_prompt: str, target_wordcount: int) -> None:
        super().__init__()

        self._state.user_prompt = user_prompt
        self._state.target_wordcount = target_wordcount

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
        count = len(text.split(" "))
        self._state.wordcount = count
        return frozenset({"_state.wordcount"})

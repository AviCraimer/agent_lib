"""Store for the exact text length example.

This store manages state for an agent that writes text to hit an exact word count.
"""

from dataclasses import dataclass

from agent_lib.store.state.State import State
from agent_lib.store.Store import Store
from agent_lib.store.StoreUpdater import store_updater
from agent_lib.util.json_utils import JSONSchema


@dataclass
class ExactLengthState(State):
    user_prompt: str = ""
    target_wordcount: int = 0
    current_text: str = ""
    wordcount: int = 0
    finished: bool = False


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


# Define Store Updaters for this app
@store_updater
def update_text(store: ExactLengthStore, new_text: str) -> frozenset[str]:
    """Update the current text."""
    store._state.current_text = new_text
    return frozenset({"_state.current_text"})


update_text.payload_json_schema = JSONSchema({"type": "string"})


@store_updater
def update_wordcount(store: ExactLengthStore, _payload: None = None) -> frozenset[str]:
    """Recalculate wordcount from current text."""
    store._state.wordcount = get_wordcount(store._state.current_text)
    return frozenset({"_state.wordcount"})


update_wordcount.payload_json_schema = JSONSchema({"type": "number"})


@store_updater
def update_finished(store: ExactLengthStore, finished: bool) -> frozenset[str]:
    """Set the finished flag."""
    store._state.finished = finished
    return frozenset({"_state.finished"})


update_finished.payload_json_schema = JSONSchema({"type": "boolean"})

# TODO: We can abstract this patters for simple setters. We just need to provide the path to the state, e.g., store.setter("_state.finished") returns a StoreUpdater

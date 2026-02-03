"""Store for the exact text length example.

This store manages state for an agent that writes text to hit an exact word count.
"""

from dataclasses import dataclass

from agent_lib.store.state.State import State

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


# Define Store Updaters for this app
@store_updater
def update_text(state: ExactLengthState, new_text: str) -> frozenset[str]:
    """Update the current text."""
    state.current_text = new_text
    return frozenset({"current_text"})


update_text.payload_json_schema = JSONSchema({"type": "string"})


@store_updater
def update_wordcount(state: ExactLengthState, _payload: None = None) -> frozenset[str]:
    """Recalculate wordcount from current text."""
    state.wordcount = get_wordcount(state.current_text)
    return frozenset({"wordcount"})


update_wordcount.payload_json_schema = JSONSchema({"type": "number"})


@store_updater
def update_finished(state: ExactLengthState, finished: bool) -> frozenset[str]:
    """Set the finished flag."""
    state.finished = finished
    return frozenset({"finished"})


update_finished.payload_json_schema = JSONSchema({"type": "boolean"})

# TODO: We can abstract this patters for simple setters. We just need to provide the path to the state, e.g., store.setter("_state.finished") returns a StoreUpdater

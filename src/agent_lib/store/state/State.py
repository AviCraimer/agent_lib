"""Base state class for Store.

State holds the observable data in a Store. Subclass to add app-specific state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_lib.store.state.AgentState import AgentState


@dataclass
class State:
    """Base state class. Subclass to add app-specific state.

    Example:
        @dataclass
        class AppState(State):
            config: dict[str, Any] = field(default_factory=dict)
            messages: list[str] = field(default_factory=list)
    """

    agent_state: dict[str, AgentState] = field(default_factory=dict)

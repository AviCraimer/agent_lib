"""StoreUpdaterBase - abstract base class for tools that mutate Store state.

StoreUpdater tools are bound to an AgentApp and have access to the Store for state
mutation. They handle the snapshot/diff/notify flow automatically.
"""

# pyright: reportPrivateUsage=false
# StoreUpdaterBase needs access to AgentApp._store for binding.

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, Self
from copy import copy


from agent_lib.tool.Tool import Tool
from agent_lib.tool.ToolMetadata import ToolMetadata

if TYPE_CHECKING:
    from agent_lib.agent_app.AgentApp import AgentApp
    from agent_lib.store.state.State import State
    from agent_lib.store.Store import Store


class StoreUpdaterBase[S: State, P](Tool[P, None], ABC):
    """Base class for tools that mutate Store state with change tracking.

    StoreUpdaters are Tools that:
    1. Have access to the Store via binding to an AgentApp
    2. Automatically handle snapshot/diff/notify flow
    3. Return None (state changes are observed via subscribers)

    Type Parameters:
        S: State type this updater operates on
        P: Payload type the updater accepts

    Note: Subclasses must implement `handler`, `__call__`, `name`, `description`,
    `payload_json_schema`, and `to_metadata()` to satisfy the Tool interface.
    """

    _app: AgentApp[S] | None
    _store: Store[S] | None
    name: str  # Unique identifier for this tool - set by subclasses

    validator: Callable[[P], Literal[True] | str] = (
        lambda p: True
    )  # Str is used in the error message

    @abstractmethod
    def to_metadata(self) -> ToolMetadata:
        """Convert to tool metadata for agent state."""
        ...

    def bind(self, app: AgentApp[S]) -> Self:
        """Bind this updater to an AgentApp.

        Must be called before the updater can be used. This gives the updater
        access to the Store for state mutation and the AgentApp for subscriber
        notifications.

        Args:
            app: The AgentApp to bind to
        """

        bound = copy(self)
        bound._app = app
        bound._store = app._store
        # TODO: Figure this out later, the new name was causing tool calls to fail to I commented it out.
        # app_name_str = f"@{app.name}"
        # clean_name = self.name.replace(app_name_str, "")
        # bound.name = f"{clean_name}@{app.name}"
        return bound

    def process_update(
        self,
        updater: Callable[[S, P], frozenset[str]],
        payload: P,
    ) -> None:
        """Execute updater with snapshot/diff/notify flow.

        This is the core mutation flow:
        1. Snapshot the store state
        2. Call the updater function to mutate state
        3. Calls set state on the store

        Args:
            updater: Function that mutates state and returns affected paths
            payload: The payload to pass to the updater

        Raises:
            RuntimeError: If the updater is not bound to an AgentApp
        """
        if self._store is None or self._app is None:
            raise RuntimeError(
                f"StoreUpdater '{self.name}' not bound. Call .bind(app) first."
            )

        if isinstance(self.validator, str):
            raise ValueError(str)

        state_snapshot = self._store.state
        scope = updater(state_snapshot, payload)  # mutates the snapshot
        self._store.set_state(state_snapshot, scope)

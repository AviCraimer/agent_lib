"""StoreUpdaterBase - abstract base class for tools that mutate Store state.

StoreUpdater tools are bound to an AgentApp and have access to the Store for state
mutation. They handle the snapshot/diff/notify flow automatically.
"""

# pyright: reportPrivateUsage=false
# StoreUpdaterBase needs access to AgentApp._store for binding.

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from deepdiff import DeepDiff, Delta, parse_path

from agent_lib.store.snapshot import snapshot
from agent_lib.tool.ToolMetadata import ToolMetadata

if TYPE_CHECKING:
    from agent_lib.agent_app.AgentApp import AgentApp
    from agent_lib.store.Store import Store


class StoreUpdaterBase[P, S: Store](ABC):
    """Base class for tools that mutate Store state with change tracking.

    StoreUpdaters are Tools that:
    1. Have access to the Store via binding to an AgentApp
    2. Automatically handle snapshot/diff/notify flow
    3. Return None (state changes are observed via subscribers)

    Type Parameters:
        P: Payload type the updater accepts
        S: Store type this updater operates on

    Note: Subclasses must implement `handler`, `__call__`, `name`, `description`,
    `payload_json_schema`, and `to_metadata()` to satisfy the Tool interface.
    """

    _app: AgentApp[S] | None
    _store: S | None
    name: str  # Unique identifier for this tool - set by subclasses

    @abstractmethod
    def to_metadata(self) -> ToolMetadata:
        """Convert to tool metadata for agent state."""
        ...

    def bind(self, app: AgentApp[S]) -> None:
        """Bind this updater to an AgentApp.

        Must be called before the updater can be used. This gives the updater
        access to the Store for state mutation and the AgentApp for subscriber
        notifications.

        Args:
            app: The AgentApp to bind to
        """
        # TODO: This should return a new instance with _app and _store set rather than returning the original instance.
        self._app = app
        self._store = app._store

    def process_update(
        self,
        updater: Callable[[S, Any], frozenset[str]],
        payload: Any,
    ) -> None:
        """Execute updater with snapshot/diff/notify flow.

        This is the core mutation flow:
        1. Snapshot the store state
        2. Call the updater function to mutate state
        3. Diff the snapshot against current state
        4. Notify subscribers of changes

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

        store_snapshot = snapshot(self._store)
        scope = updater(self._store, payload)

        if not scope:  # no-op
            return

        # "." means full diff, otherwise filter to specified scope paths
        if "." in scope:
            diff = DeepDiff(store_snapshot, self._store)
        else:
            diff = DeepDiff(
                store_snapshot,
                self._store,
                include_obj_callback=self.make_scope_filter(scope),
            )

        delta = Delta(diff)
        self._app.subscribers.notify(delta)

    @staticmethod
    def make_scope_filter(
        scopes: frozenset[str],
    ) -> Callable[[object, str], bool]:
        """Create a DeepDiff include_obj_callback that filters to given scopes.

        Args:
            scopes: Set of dot-notation paths, e.g., {'data.user_info', 'config'}

        Returns:
            Callback function for DeepDiff's include_obj_callback parameter
        """

        def callback(_obj: object, path: str) -> bool:
            # Normalize DeepDiff path (e.g., root.data['key']) to dot notation
            # parse_path returns strings for keys and ints for list indices
            normalized = ".".join(str(p) for p in parse_path(path))
            if not normalized:  # root - always traverse
                return True
            for scope in scopes:
                # Include if path is within scope OR scope is within path (for traversal)
                if normalized.startswith(scope) or scope.startswith(normalized):
                    return True
            return False

        return callback

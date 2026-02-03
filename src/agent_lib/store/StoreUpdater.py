"""StoreUpdater - a Tool that mutates Store state synchronously.

StoreUpdater replaces the Action pattern with a unified Tool-based approach.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar, overload

from agent_lib.store.state.State import State
from agent_lib.store.StoreUpdaterBase import StoreUpdaterBase
from agent_lib.tool.ToolMetadata import ToolMetadata
from agent_lib.util.json_utils import JSONSchema


@dataclass
class StoreUpdater[S: State, P](StoreUpdaterBase[S, P]):
    """A Tool that mutates Store state synchronously with change tracking.

    StoreUpdater combines the tool interface with state mutation, replacing the
    separate Action + action_to_tool pattern.

    Type Parameters:
        S: State type this updater operates on
        P: Payload type the updater accepts

    Attributes:
        name: Unique identifier for this tool
        description: Human-readable description (useful for LLM tool selection)
        payload_json_schema: JSON schema describing the payload format
        updater: Function that receives (store, payload) and returns affected paths
    """

    class scope:
        """Helper constants for updater return values (avoid magic strings)."""

        no_op: ClassVar[frozenset[str]] = frozenset()
        """Return this when updater made no changes - skips diff and notifications."""

        full_diff: ClassVar[frozenset[str]] = frozenset({"."})
        """Return this when scope is unknown - diffs entire state tree."""

    name: str
    description: str
    payload_json_schema: JSONSchema
    updater: Callable[[S, P], frozenset[str]]
    _app: Any = field(default=None, repr=False)
    _store: Any = field(default=None, repr=False)

    @property
    def handler(self) -> Callable[[P], None]:
        """Tool handler that routes through process_update."""

        def _handler(payload: P) -> None:
            self.process_update(self.updater, payload)

        return _handler

    def __call__(self, payload: P) -> None:
        """Invoke the updater with the given payload."""
        self.handler(payload)

    # TODO: This to_metadata method looks like it should be a default implementation on the Tool class.
    def to_metadata(self) -> ToolMetadata:
        """Convert to tool metadata for agent state."""
        return ToolMetadata(
            name=self.name,
            description=self.description,
            payload_json_schema=self.payload_json_schema,
        )


# ***STORE UPDATER DECORATOR***
@overload
def store_updater[S: State, P](
    handler: Callable[[S, P], frozenset[str]],
    *,
    schema: JSONSchema | None = None,
) -> StoreUpdater[S, P]: ...


@overload
def store_updater[S: State, P](
    handler: None = ...,
    *,
    schema: JSONSchema | None = None,
) -> Callable[[Callable[[S, P], frozenset[str]]], StoreUpdater[S, P]]: ...


def store_updater[S: State, P](
    handler: Callable[[S, P], frozenset[str]] | None = None,
    *,
    schema: JSONSchema | None = None,
) -> (
    StoreUpdater[S, P]
    | Callable[[Callable[[S, P], frozenset[str]]], StoreUpdater[S, P]]
):
    """Decorator to create a StoreUpdater from a handler function.

    This provides a convenient way to define StoreUpdaters inline. The handler
    function receives (store, payload) and should mutate the store state,
    returning a frozenset of affected paths for efficient diffing.

    Usage:
        @store_updater
        def update_text(store: MyStore, new_text: str) -> frozenset[str]:
            store._state.current_text = new_text
            return frozenset({"_state.current_text"})

        # Later, bind and  grant:
        update_text.bind(app)
        app.grant_tool("writer", update_text)"""

    def wrap(fn: Callable[[S, P], frozenset[str]]) -> StoreUpdater[S, P]:
        return StoreUpdater(
            name=fn.__name__,
            description=fn.__doc__ or "",
            payload_json_schema=schema or JSONSchema({}),
            updater=fn,
        )

    return wrap if handler is None else wrap(handler)

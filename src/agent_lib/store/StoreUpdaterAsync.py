"""StoreUpdaterAsync - a Tool that performs async work then mutates Store state.

StoreUpdaterAsync replaces the AsyncAction pattern with a unified Tool-based approach.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Self

from agent_lib.agent_app.AgentApp import AgentApp
from agent_lib.store.StoreUpdater import StoreUpdater
from agent_lib.store.state.State import State
from agent_lib.store.StoreUpdaterBase import StoreUpdaterBase
from agent_lib.tool.ToolMetadata import ToolMetadata
from agent_lib.util.json_utils import JSONSchema


@dataclass
class StoreUpdaterAsync[
    S: State,
    P,
    R,
](StoreUpdaterBase[S, P]):
    """A Tool that performs async work then mutates Store state.

    StoreUpdaterAsync separates async work (which may fail) from state mutation
    (which should be synchronous and predictable). This pattern ensures:
    - Async work runs first, can fail early
    - State mutation happens only after async work succeeds
    - Snapshot/diff/notify flow runs around the sync mutation

    Type Parameters:
        S: State type this updater operates on
        P: Payload type the updater accepts
        R: Result type returned by async_handler and passed to on_success

    Parent Class:
        StoreUpdaterBase[S, Exception] because we use the default implementation of `process_update` only on error with the Exception as the payload. For success we call the on_success updater directly.

    Attributes:
        name: Unique identifier for this tool
        description: Human-readable description
        payload_json_schema: JSON schema describing the payload format
        async_handler: Async function that does read-only work and returns result
        on_success: A synchronous updater that is called with the result of a succesful async call as a payload.
        on_error: Optional sync function that handles errors by mutating state
    """

    name: str
    description: str
    payload_json_schema: JSONSchema
    async_handler: Callable[[S, P], Coroutine[Any, Any, R]]
    on_success: StoreUpdater[S, R]
    on_error: StoreUpdater[S, Exception] | None = None
    _app: Any = field(default=None, repr=False)
    _store: Any = field(default=None, repr=False)

    @property
    def handler(self) -> Callable[[P], Coroutine[Any, Any, None]]:
        """Tool handler that routes through async flow."""

        async def _handler(payload: P) -> None:
            if self._store is None or self._app is None:
                raise RuntimeError(f"StoreUpdaterAsync '{self.name}' not bound.")
            try:
                result = await self.async_handler(self._store, payload)
                self.on_success(result)
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
                else:
                    raise e

        return _handler

    def __call__(self, payload: P) -> Coroutine[Any, Any, None]:
        """Invoke the tool with the given payload."""
        return self.handler(payload)

    def to_metadata(self) -> ToolMetadata:
        """Convert to tool metadata for agent state."""
        return ToolMetadata(
            name=self.name,
            description=self.description,
            payload_json_schema=self.payload_json_schema,
        )

    def bind(self, app: AgentApp[S]) -> Self:
        """Ensures that on_success handler is bound the app, this avoids having to bind it seprately."""
        bound = super().bind(app)
        bound.on_success = self.on_success.bind(app)
        return bound

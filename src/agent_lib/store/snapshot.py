"""Snapshot utility for creating deep copies of state.

This module wraps the snapshot implementation to allow easy swapping
of the underlying copy mechanism. Current implementation uses `copy.deepcopy`.

Alternative implementations to consider for performance optimization:
- `duper` - faster deepcopy for dataclasses
- `pickle` + `unpickle` - fast for pickle-compatible objects
- `orjson` - serialize/deserialize for JSON-compatible state

To swap implementation, modify the `snapshot()` function body.
"""

from __future__ import annotations

import copy


def snapshot[S](state: S) -> S:
    """Create a deep copy of the state for change detection.

    Args:
        state: The state object to snapshot

    Returns:
        A deep copy of the state that can be compared against later
    """
    return copy.deepcopy(state)

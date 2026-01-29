"""Tests for scope filtering behavior in StoreUpdaters.

Tests the frozenset scope return values:
- Empty frozenset (no_op) - no diff, no notification
- Single path - diff only that path
- Multiple paths - diff all specified paths
- "." (full_diff) - diff entire store
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_lib.agent_app.AgentApp import AgentApp
from agent_lib.store.Store import Store
from agent_lib.store.StoreUpdater import StoreUpdater
from agent_lib.util.json_utils import JSONSchema


class TestNoOpScope:
    """Tests for empty frozenset (no_op) scope behavior."""

    def test_no_op_returns_empty_delta(self) -> None:
        """Updater returning empty frozenset produces no notification."""

        class NoOpStore(Store):
            value: str

            def __init__(self) -> None:
                self.value = "initial"
                super().__init__()

        def _no_change_handler(store: NoOpStore, _: None) -> frozenset[str]:
            return frozenset()  # no_op

        no_change_updater: StoreUpdater[None, NoOpStore] = StoreUpdater(
            name="no_change",
            description="Does nothing.",
            payload_json_schema=JSONSchema({}),
            updater=_no_change_handler,
        )

        store = NoOpStore()
        app: AgentApp[NoOpStore] = AgentApp(store)
        no_change_updater.bind(app)

        notification_count = 0

        def on_change(_: Callable[[str], bool]) -> None:
            nonlocal notification_count
            notification_count += 1

        app.subscribers.append(on_change)

        no_change_updater(None)

        assert notification_count == 0

    def test_no_op_when_value_unchanged(self) -> None:
        """Returning no_op when value didn't actually change."""

        class ConditionalStore(Store):
            name: str

            def __init__(self) -> None:
                self.name = "Alice"
                super().__init__()

        def _set_name_handler(store: ConditionalStore, new_name: str) -> frozenset[str]:
            if store.name == new_name:
                return frozenset()  # no_op - same value
            store.name = new_name
            return frozenset({"name"})

        set_name_updater: StoreUpdater[str, ConditionalStore] = StoreUpdater(
            name="set_name",
            description="Set the name.",
            payload_json_schema=JSONSchema({}),
            updater=_set_name_handler,
        )

        store = ConditionalStore()
        app: AgentApp[ConditionalStore] = AgentApp(store)
        set_name_updater.bind(app)

        notification_count = 0

        def on_change(_: Callable[[str], bool]) -> None:
            nonlocal notification_count
            notification_count += 1

        app.subscribers.append(on_change)

        # Same value - should not notify
        set_name_updater("Alice")
        assert notification_count == 0

        # Different value - should notify
        set_name_updater("Bob")
        assert notification_count == 1


class TestFullDiffScope:
    """Tests for '.' (full_diff) scope behavior."""

    def test_full_diff_captures_all_changes(self) -> None:
        """Updater returning '.' triggers full diff of entire store."""

        class FullDiffStore(Store):
            name: str
            count: int
            active: bool

            def __init__(self) -> None:
                self.name = "initial"
                self.count = 0
                self.active = False
                super().__init__()

        def _update_all_handler(store: FullDiffStore, new_name: str) -> frozenset[str]:
            store.name = new_name
            store.count = 999
            store.active = True
            return frozenset({"."})  # full diff

        update_all_updater: StoreUpdater[str, FullDiffStore] = StoreUpdater(
            name="update_all",
            description="Update all fields.",
            payload_json_schema=JSONSchema({}),
            updater=_update_all_handler,
        )

        store = FullDiffStore()
        app: AgentApp[FullDiffStore] = AgentApp(store)
        update_all_updater.bind(app)

        affected_checks: list[tuple[bool, bool, bool]] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            affected_checks.append((affects("name"), affects("count"), affects("active")))

        app.subscribers.append(on_change)

        update_all_updater("updated")

        assert store.name == "updated"
        assert store.count == 999
        assert store.active is True
        assert len(affected_checks) == 1
        # Full diff should capture all three changes
        assert affected_checks[0] == (True, True, True)


class TestMultipleScopePaths:
    """Tests for multiple paths in scope frozenset."""

    def test_two_scope_paths(self) -> None:
        """Updater returning multiple scope paths diffs all of them."""

        class MultiPathStore(Store):
            data: dict[str, Any]
            config: dict[str, Any]
            heavy: dict[str, Any]  # Should not be diffed

            def __init__(self) -> None:
                self.data = {}
                self.config = {}
                self.heavy = {f"key_{i}": i for i in range(100)}
                super().__init__()

        def update_both_handler(
            store: MultiPathStore, payload: tuple[str, str]
        ) -> frozenset[str]:
            data_val, config_val = payload
            store.data["user"] = data_val
            store.config["theme"] = config_val
            return frozenset({"data.user", "config.theme"})

        update_both_updater: StoreUpdater[tuple[str, str], MultiPathStore] = StoreUpdater(
            name="update_both",
            description="Update both data and config.",
            payload_json_schema=JSONSchema({}),
            updater=update_both_handler,
        )

        store = MultiPathStore()
        app: AgentApp[MultiPathStore] = AgentApp(store)
        update_both_updater.bind(app)

        affected_checks: list[tuple[bool, bool, bool]] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            affected_checks.append(
                (affects("data.user"), affects("config.theme"), affects("heavy"))
            )

        app.subscribers.append(on_change)

        update_both_updater(("alice", "dark"))

        assert store.data["user"] == "alice"
        assert store.config["theme"] == "dark"
        assert len(affected_checks) == 1
        # Both paths affected, heavy not affected
        assert affected_checks[0] == (True, True, False)

    def test_nested_scope_paths(self) -> None:
        """Nested dot-notation paths work correctly."""

        class NestedStore(Store):
            users: dict[str, dict[str, Any]]
            settings: dict[str, Any]

            def __init__(self) -> None:
                self.users = {"alice": {"name": "Alice", "age": 30}}
                self.settings = {"theme": "light"}
                super().__init__()

        def update_user_name_handler(store: NestedStore, new_name: str) -> frozenset[str]:
            store.users["alice"]["name"] = new_name
            return frozenset({"users.alice.name"})

        update_user_name_updater: StoreUpdater[str, NestedStore] = StoreUpdater(
            name="update_user_name",
            description="Update user's name.",
            payload_json_schema=JSONSchema({}),
            updater=update_user_name_handler,
        )

        store = NestedStore()
        app: AgentApp[NestedStore] = AgentApp(store)
        update_user_name_updater.bind(app)

        affected_checks: list[tuple[bool, bool, bool]] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            affected_checks.append(
                (affects("users.alice.name"), affects("users.alice.age"), affects("settings"))
            )

        app.subscribers.append(on_change)

        update_user_name_updater("Alicia")

        assert store.users["alice"]["name"] == "Alicia"
        assert len(affected_checks) == 1
        # Only name affected, not age or settings
        assert affected_checks[0] == (True, False, False)

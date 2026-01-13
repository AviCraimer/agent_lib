"""Tests for scope filtering behavior in Store actions.

Tests the frozenset scope return values:
- Empty frozenset (no_op) - no diff, no notification
- Single path - diff only that path
- Multiple paths - diff all specified paths
- "." (full_diff) - diff entire store
"""

from __future__ import annotations

from typing import Any

from deepdiff import Delta

from agent_lib.store.Action import Action
from agent_lib.store.Store import Store


class TestNoOpScope:
    """Tests for empty frozenset (no_op) scope behavior."""

    def test_no_op_returns_empty_delta(self) -> None:
        """Action returning empty frozenset produces no notification."""

        class NoOpStore(Store):
            value: str

            def __init__(self) -> None:
                self.value = "initial"
                super().__init__()

            @Store.action
            def no_change(self, _: None) -> frozenset[str]:
                return frozenset()  # no_op

        store = NoOpStore()
        notifications: list[Delta] = []
        store.subscribe(lambda d: notifications.append(d))

        store.no_change(None)

        assert len(notifications) == 0

    def test_no_op_when_value_unchanged(self) -> None:
        """Returning no_op when value didn't actually change."""

        class ConditionalStore(Store):
            name: str

            def __init__(self) -> None:
                self.name = "Alice"
                super().__init__()

            @Store.action
            def set_name(self, new_name: str) -> frozenset[str]:
                if self.name == new_name:
                    return frozenset()  # no_op - same value
                self.name = new_name
                return frozenset({"name"})

        store = ConditionalStore()
        notifications: list[Delta] = []
        store.subscribe(lambda d: notifications.append(d))

        # Same value - should not notify
        store.set_name("Alice")
        assert len(notifications) == 0

        # Different value - should notify
        store.set_name("Bob")
        assert len(notifications) == 1


class TestFullDiffScope:
    """Tests for '.' (full_diff) scope behavior."""

    def test_full_diff_captures_all_changes(self) -> None:
        """Action returning '.' triggers full diff of entire store."""

        class FullDiffStore(Store):
            name: str
            count: int
            active: bool

            def __init__(self) -> None:
                self.name = "initial"
                self.count = 0
                self.active = False
                super().__init__()

            @Store.action
            def update_all(self, new_name: str) -> frozenset[str]:
                self.name = new_name
                self.count = 999
                self.active = True
                return frozenset({"."})  # full diff

        store = FullDiffStore()
        notifications: list[Delta] = []
        store.subscribe(lambda d: notifications.append(d))

        store.update_all("updated")

        assert store.name == "updated"
        assert store.count == 999
        assert store.active is True
        assert len(notifications) == 1

        # Full diff should capture all three changes
        diff_str = str(notifications[0].diff)
        assert "updated" in diff_str
        assert "999" in diff_str


class TestMultipleScopePaths:
    """Tests for multiple paths in scope frozenset."""

    def test_two_scope_paths(self) -> None:
        """Action returning multiple scope paths diffs all of them."""

        class MultiPathStore(Store):
            data: dict[str, Any]
            config: dict[str, Any]
            heavy: dict[str, Any]  # Should not be diffed

            def __init__(self) -> None:
                self.data = {}
                self.config = {}
                self.heavy = {f"key_{i}": i for i in range(100)}
                super().__init__()

        def update_both(
            store: MultiPathStore, payload: tuple[str, str]
        ) -> frozenset[str]:
            data_val, config_val = payload
            store.data["user"] = data_val
            store.config["theme"] = config_val
            return frozenset({"data.user", "config.theme"})

        update_action = Action[MultiPathStore, tuple[str, str]](handler=update_both)

        class TestStore(MultiPathStore):
            update_both = update_action

        store = TestStore()
        notifications: list[Delta] = []
        store.subscribe(lambda d: notifications.append(d))

        store.update_both(("alice", "dark"))

        assert store.data["user"] == "alice"
        assert store.config["theme"] == "dark"
        assert len(notifications) == 1

        # Verify both changes captured
        diff_str = str(notifications[0].diff)
        assert "alice" in diff_str
        assert "dark" in diff_str

    def test_nested_scope_paths(self) -> None:
        """Nested dot-notation paths work correctly."""

        class NestedStore(Store):
            users: dict[str, dict[str, Any]]
            settings: dict[str, Any]

            def __init__(self) -> None:
                self.users = {"alice": {"name": "Alice", "age": 30}}
                self.settings = {"theme": "light"}
                super().__init__()

            @Store.action
            def update_user_name(self, new_name: str) -> frozenset[str]:
                self.users["alice"]["name"] = new_name
                return frozenset({"users.alice.name"})

        store = NestedStore()
        notifications: list[Delta] = []
        store.subscribe(lambda d: notifications.append(d))

        store.update_user_name("Alicia")

        assert store.users["alice"]["name"] == "Alicia"
        assert len(notifications) == 1
        diff_str = str(notifications[0].diff)
        assert "Alicia" in diff_str

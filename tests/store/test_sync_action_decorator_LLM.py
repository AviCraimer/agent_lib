"""Tests for @Store.action decorator pattern."""

from __future__ import annotations

from deepdiff import Delta

from agent_lib.store.Store import Store


class TestSyncActionDecorator:
    """Tests for @Store.action decorator creating sync actions."""

    def test_store_action_decorator_basic(self) -> None:
        """@Store.action decorator creates working sync action."""

        class CounterStore(Store):
            count: int

            def __init__(self) -> None:
                self.count = 0
                super().__init__()

            @Store.action
            def increment(self, amount: int) -> frozenset[str]:
                self.count += amount
                return frozenset({"count"})

        store = CounterStore()
        notifications: list[Delta] = []
        store.subscribe(lambda d: notifications.append(d))

        store.increment(5)

        assert store.count == 5
        assert len(notifications) == 1

    def test_action_mutates_state(self) -> None:
        """Action handler mutates the store state."""

        class NameStore(Store):
            name: str

            def __init__(self) -> None:
                self.name = "initial"
                super().__init__()

            @Store.action
            def set_name(self, new_name: str) -> frozenset[str]:
                self.name = new_name
                return frozenset({"name"})

        store = NameStore()

        store.set_name("updated")

        assert store.name == "updated"

    def test_action_delta_contains_change(self) -> None:
        """Delta from action contains the correct change info."""

        class ValueStore(Store):
            value: int

            def __init__(self) -> None:
                self.value = 10
                super().__init__()

            @Store.action
            def set_value(self, new_value: int) -> frozenset[str]:
                self.value = new_value
                return frozenset({"value"})

        store = ValueStore()
        notifications: list[Delta] = []
        store.subscribe(lambda d: notifications.append(d))

        store.set_value(42)

        assert len(notifications) == 1
        diff_str = str(notifications[0].diff)
        assert "42" in diff_str

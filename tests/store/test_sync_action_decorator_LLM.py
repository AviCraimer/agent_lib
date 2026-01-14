"""Tests for @Store.action decorator pattern."""

from __future__ import annotations

from collections.abc import Callable

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
        notifications: list[bool] = []
        store.subscribe(lambda affects: notifications.append(affects("count")))

        store.increment(5)

        assert store.count == 5
        assert len(notifications) == 1
        assert notifications[0] is True  # count was affected

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

    def test_action_notifies_on_change(self) -> None:
        """Action correctly notifies subscriber when value changes."""

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
        affected_paths: list[tuple[bool, bool]] = []

        def on_change(affects: Callable[[str], bool]) -> None:
            affected_paths.append((affects("value"), affects("other")))

        store.subscribe(on_change)

        store.set_value(42)

        assert store.value == 42
        assert len(affected_paths) == 1
        assert affected_paths[0] == (True, False)  # value affected, other not

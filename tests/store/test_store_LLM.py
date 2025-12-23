"""Tests for Store._process_action() and Delta-based change detection."""

# pyright: reportPrivateUsage=false

from dataclasses import dataclass

from agent_lib.store.Action import Action
from agent_lib.store.Store import Store


@dataclass
class AppState:
    name: str
    count: int


class AppStore(Store[AppState]):
    @Store.action
    @staticmethod
    def set_name(state: AppState, name: str) -> frozenset[str]:
        if state.name == name:
            return Action.scope.no_op
        state.name = name
        return frozenset({"name"})

    @Store.action
    @staticmethod
    def increment(state: AppState, amount: int) -> frozenset[str]:
        state.count += amount
        return frozenset({"count"})

    @Store.action
    @staticmethod
    def no_change(state: AppState, _: None) -> frozenset[str]:
        return Action.scope.no_op

    @Store.action
    @staticmethod
    def full_update(state: AppState, new_name: str) -> frozenset[str]:
        state.name = new_name
        state.count = 999
        return Action.scope.full_diff


class TestProcessAction:
    """Tests for Store._process_action()"""

    def test_specific_path_returns_delta_with_change(self) -> None:
        """Action returning specific path produces Delta with that change."""
        store = AppStore(AppState(name="Alice", count=0))

        delta = store._process_action(AppStore.set_name.handler, "Bob")

        assert delta.diff  # non-empty
        # Delta should contain the name change
        flat_rows = list(delta.to_flat_rows())
        assert len(flat_rows) == 1
        assert flat_rows[0].value == "Bob"

    def test_no_op_returns_empty_delta(self) -> None:
        """Action returning no_op produces empty Delta."""
        store = AppStore(AppState(name="Alice", count=0))

        delta = store._process_action(AppStore.no_change.handler, None)

        assert not delta.diff  # empty dict = no changes

    def test_no_op_when_value_unchanged(self) -> None:
        """Action returning no_op when value didn't change produces empty Delta."""
        store = AppStore(AppState(name="Alice", count=0))

        # Setting name to same value should return no_op
        delta = store._process_action(AppStore.set_name.handler, "Alice")

        assert not delta.diff

    def test_full_diff_diffs_entire_state(self) -> None:
        """Action returning full_diff produces Delta with all changes."""
        store = AppStore(AppState(name="Alice", count=0))

        delta = store._process_action(AppStore.full_update.handler, "Bob")

        assert delta.diff  # non-empty
        flat_rows = list(delta.to_flat_rows())
        # Should have 2 changes: name and count
        assert len(flat_rows) == 2
        paths = {tuple(row.path) for row in flat_rows}
        assert ("name",) in paths
        assert ("count",) in paths

    def test_state_is_mutated(self) -> None:
        """_process_action actually mutates the state."""
        store = AppStore(AppState(name="Alice", count=0))

        store._process_action(AppStore.set_name.handler, "Bob")

        assert store.get().name == "Bob"

    def test_increment_produces_correct_delta(self) -> None:
        """Numeric changes are captured in Delta."""
        store = AppStore(AppState(name="Alice", count=5))

        delta = store._process_action(AppStore.increment.handler, 3)

        assert delta.diff
        flat_rows = list(delta.to_flat_rows())
        assert len(flat_rows) == 1
        assert flat_rows[0].value == 8  # 5 + 3
        assert store.get().count == 8

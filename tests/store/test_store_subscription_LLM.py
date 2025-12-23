"""Tests for Store.subscribe() and notification system."""

from deepdiff import Delta

from test_store_LLM import AppState, AppStore


class TestSubscriptions:
    """Tests for Store.subscribe() and notification system"""

    def test_subscribe_receives_delta_on_action(self) -> None:
        """Subscriber callback receives Delta when action triggers change."""
        store = AppStore(AppState(name="Alice", count=0))
        received_deltas: list[Delta] = []

        store.subscribe(lambda delta: received_deltas.append(delta))
        store.set_name("Bob")

        assert len(received_deltas) == 1
        assert received_deltas[0].diff  # non-empty delta

    def test_unsubscribe_stops_callbacks(self) -> None:
        """After unsubscribe, callback is no longer called."""
        store = AppStore(AppState(name="Alice", count=0))
        call_count = 0

        def callback(delta: Delta) -> None:
            nonlocal call_count
            call_count += 1

        unsubscribe = store.subscribe(callback)
        store.set_name("Bob")
        assert call_count == 1

        unsubscribe()
        store.set_name("Charlie")
        assert call_count == 1  # still 1, not called again

    def test_no_op_action_does_not_trigger_subscribers(self) -> None:
        """Actions returning no_op don't notify subscribers."""
        store = AppStore(AppState(name="Alice", count=0))

        # Use a mutable to track calls
        calls: list[int] = []
        store.subscribe(lambda _: calls.append(1) or None)

        # Action that returns no_op
        store.no_change(None)
        assert len(calls) == 0

        # Same value = no_op
        store.set_name("Alice")
        assert len(calls) == 0

    def test_multiple_subscribers_all_notified(self) -> None:
        """All subscribers receive the Delta."""
        store = AppStore(AppState(name="Alice", count=0))
        calls_1: list[Delta] = []
        calls_2: list[Delta] = []

        store.subscribe(lambda d: calls_1.append(d))
        store.subscribe(lambda d: calls_2.append(d))

        store.set_name("Bob")

        assert len(calls_1) == 1
        assert len(calls_2) == 1
        # Both received the same delta
        assert calls_1[0].diff == calls_2[0].diff

    def test_subscriber_receives_correct_change_info(self) -> None:
        """Subscriber can inspect Delta to see what changed."""
        store = AppStore(AppState(name="Alice", count=0))
        received: list[Delta] = []

        store.subscribe(lambda d: received.append(d))
        store.increment(5)

        assert len(received) == 1
        flat_rows = list(received[0].to_flat_rows())
        assert len(flat_rows) == 1
        assert flat_rows[0].value == 5  # new count value

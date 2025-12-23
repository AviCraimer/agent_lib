"""Tests for AsyncAction and Store async action support."""

# pyright: reportPrivateUsage=false

import pytest
from dataclasses import dataclass

from deepdiff import Delta

from agent_lib.store.Store import Store


@dataclass
class AppState:
    result: str
    error: str
    count: int


# Handlers defined externally (as per plan's recommended pattern)
def set_result(state: AppState, text: str) -> frozenset[str]:
    state.result = text
    return frozenset({"result"})


def set_error(state: AppState, error: Exception) -> frozenset[str]:
    state.error = str(error)
    return frozenset({"error"})


class AsyncStore(Store[AppState]):
    @Store.async_action(on_success=set_result, on_error=set_error)
    @staticmethod
    async def fetch_data(state: AppState, url: str) -> str:
        # Simulate async work
        return f"fetched:{url}"

    @Store.async_action(on_success=set_result)  # no on_error
    @staticmethod
    async def fetch_no_error_handler(state: AppState, url: str) -> str:
        return f"fetched:{url}"

    @Store.async_action(on_success=set_result, on_error=set_error)
    @staticmethod
    async def fetch_failing(state: AppState, _: str) -> str:
        raise ValueError("network error")

    @Store.async_action(on_success=set_result)  # no on_error - will propagate
    @staticmethod
    async def fetch_failing_no_handler(state: AppState, _: str) -> str:
        raise ValueError("network error")


class TestAsyncActionSuccess:
    """Tests for successful async action execution."""

    @pytest.mark.asyncio
    async def test_async_success_updates_state(self) -> None:
        """Async action result is passed to on_success which updates state."""
        store = AsyncStore(AppState(result="", error="", count=0))

        await store.fetch_data("http://example.com")

        assert store.get().result == "fetched:http://example.com"

    @pytest.mark.asyncio
    async def test_async_success_notifies_subscribers(self) -> None:
        """Subscribers receive Delta when async action succeeds."""
        store = AsyncStore(AppState(result="", error="", count=0))
        received_deltas: list[Delta] = []

        store.subscribe(lambda d: received_deltas.append(d))
        await store.fetch_data("http://example.com")

        assert len(received_deltas) == 1
        assert received_deltas[0].diff  # non-empty

    @pytest.mark.asyncio
    async def test_async_action_returns_none(self) -> None:
        """Bound async action returns None (not the result)."""
        store = AsyncStore(AppState(result="", error="", count=0))

        result = await store.fetch_data("http://example.com")

        assert result is None


class TestAsyncActionError:
    """Tests for async action error handling."""

    @pytest.mark.asyncio
    async def test_async_error_triggers_on_error(self) -> None:
        """When async handler raises, on_error is called to update state."""
        store = AsyncStore(AppState(result="", error="", count=0))

        await store.fetch_failing("http://example.com")

        assert store.get().error == "network error"
        assert store.get().result == ""  # unchanged

    @pytest.mark.asyncio
    async def test_async_error_notifies_subscribers(self) -> None:
        """Subscribers receive Delta when on_error updates state."""
        store = AsyncStore(AppState(result="", error="", count=0))
        received_deltas: list[Delta] = []

        store.subscribe(lambda d: received_deltas.append(d))
        await store.fetch_failing("http://example.com")

        assert len(received_deltas) == 1

    @pytest.mark.asyncio
    async def test_async_error_reraises_without_on_error(self) -> None:
        """When async handler raises and no on_error, exception propagates."""
        store = AsyncStore(AppState(result="", error="", count=0))

        with pytest.raises(ValueError, match="network error"):
            await store.fetch_failing_no_handler("will_fail")

    @pytest.mark.asyncio
    async def test_async_error_reraises_without_on_error_impl(self) -> None:
        """Verify exception propagates when on_error not provided."""

        # Create a store with action that has no on_error
        class NoErrorHandlerStore(Store[AppState]):
            @Store.async_action(on_success=set_result)  # no on_error
            @staticmethod
            async def fetch_failing(state: AppState, _: str) -> str:
                raise RuntimeError("unexpected error")

        store = NoErrorHandlerStore(AppState(result="", error="", count=0))

        with pytest.raises(RuntimeError, match="unexpected error"):
            await store.fetch_failing("test")


class TestAsyncActionReadOnly:
    """Tests verifying async handlers are read-only."""

    @pytest.mark.asyncio
    async def test_async_can_read_state(self) -> None:
        """Async handler can read current state."""

        class ReadingStore(Store[AppState]):
            @Store.async_action(on_success=set_result)
            @staticmethod
            async def read_and_return(state: AppState, prefix: str) -> str:
                # Read state during async execution
                return f"{prefix}:{state.count}"

        store = ReadingStore(AppState(result="", error="", count=42))
        await store.read_and_return("value")

        assert store.get().result == "value:42"

    @pytest.mark.asyncio
    async def test_async_mutations_not_diffed(self) -> None:
        """Mutations in async handler don't go through diff/notify flow.

        This is the expected (if not ideal) behavior - async handlers
        SHOULD be read-only, but if they mutate, those changes won't
        trigger subscribers because no snapshot is taken during async work.
        """

        class MutatingStore(Store[AppState]):
            @Store.async_action(on_success=set_result)
            @staticmethod
            async def mutate_during_async(state: AppState, _: str) -> str:
                # BAD: mutating in async handler (but we test it's not diffed)
                state.count = 999
                return "done"

        store = MutatingStore(AppState(result="", error="", count=0))
        received_deltas: list[Delta] = []
        store.subscribe(lambda d: received_deltas.append(d))

        await store.mutate_during_async("test")

        # State WAS mutated (side effect happened)
        assert store.get().count == 999
        assert store.get().result == "done"
        # But only the on_success change triggered subscriber
        assert len(received_deltas) == 1
        flat_rows = list(received_deltas[0].to_flat_rows())
        # Delta contains "done" (result change) but NOT 999 (count change)
        values = [row.value for row in flat_rows]
        assert "done" in values
        assert 999 not in values

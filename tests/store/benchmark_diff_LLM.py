"""Performance benchmarks for Store diffing.

Run with: python -m pytest tests/store/benchmark_diff_LLM.py -v -s
Or directly: python tests/store/benchmark_diff_LLM.py
"""

# pyright: reportMissingParameterType=false
# pyright: reportUnknownLambdaType=false
# pyright: reportUnknownParameterType=false
# pyright: reportUnknownMemberType=false
# pyright: reportMissingTypeArgument=false

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import pytest
from deepdiff import Delta

from agent_lib.store.Action import Action
from agent_lib.store.Store import Store


@dataclass
class Message:
    role: str
    content: str


@dataclass
class BenchmarkState:
    """State sized for realistic AI app benchmarking."""

    language: str = "en"
    user_id: str = "user123"
    messages: list[Message] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    cache: dict[str, str] = field(default_factory=dict)


def create_state(num_messages: int, num_documents: int, doc_size: int = 2000) -> BenchmarkState:
    """Create a state with specified size."""
    state = BenchmarkState()
    state.messages = [
        Message(role="user" if i % 2 == 0 else "assistant", content="x" * 500)
        for i in range(num_messages)
    ]
    state.documents = [f"doc_content_{'x' * doc_size}" for _ in range(num_documents)]
    state.cache = {f"key_{i}": f"value_{i}" * 50 for i in range(50)}
    return state


class BenchmarkStore(Store[BenchmarkState]):
    """Store for benchmarking."""

    @Store.action
    @staticmethod
    def set_language(state: BenchmarkState, lang: str) -> frozenset[str]:
        state.language = lang
        return frozenset({"language"})

    @Store.action
    @staticmethod
    def add_message(state: BenchmarkState, content: str) -> frozenset[str]:
        state.messages.append(Message(role="user", content=content))
        return frozenset({"messages"})

    @Store.action
    @staticmethod
    def full_update(state: BenchmarkState, lang: str) -> frozenset[str]:
        state.language = lang
        return Action.scope.full_diff


def benchmark_action(
    store_factory: Callable[[], Store[Any]],
    action_fn: Callable[[Store[Any], Any], None],
    payload: Any,
    iterations: int = 100,
) -> dict[str, float]:
    """Benchmark an action and return timing stats."""
    times = []
    for _ in range(iterations):
        store = store_factory()
        start = time.perf_counter()
        action_fn(store, payload)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    times_us = [t * 1_000_000 for t in times]
    return {
        "avg_us": sum(times_us) / len(times_us),
        "min_us": min(times_us),
        "max_us": max(times_us),
        "p99_us": sorted(times_us)[int(len(times_us) * 0.99)],
    }


class TestDiffPerformance:
    """Performance benchmarks for diff operations."""

    @pytest.mark.benchmark
    def test_small_state_scoped_diff(self) -> None:
        """Small state (10 msgs): scoped diff should be < 1ms."""

        def factory():
            return BenchmarkStore(create_state(num_messages=10, num_documents=5))

        def action(store, payload):
            store.set_language(payload)

        stats = benchmark_action(factory, action, "es", iterations=200)

        print(f"\nSmall state scoped diff: avg={stats['avg_us']:.0f}µs p99={stats['p99_us']:.0f}µs")
        assert stats["avg_us"] < 1000, f"Scoped diff too slow: {stats['avg_us']}µs"

    @pytest.mark.benchmark
    def test_medium_state_scoped_diff(self) -> None:
        """Medium state (50 msgs, 30 docs): scoped diff should be < 5ms."""

        def factory():
            return BenchmarkStore(create_state(num_messages=50, num_documents=30))

        def action(store, payload):
            store.set_language(payload)

        stats = benchmark_action(factory, action, "es", iterations=100)

        print(f"\nMedium state scoped diff: avg={stats['avg_us']:.0f}µs p99={stats['p99_us']:.0f}µs")
        assert stats["avg_us"] < 5000, f"Scoped diff too slow: {stats['avg_us']}µs"

    @pytest.mark.benchmark
    def test_large_state_scoped_diff(self) -> None:
        """Large state (100 msgs, 50 docs): scoped diff should be < 10ms."""

        def factory():
            return BenchmarkStore(create_state(num_messages=100, num_documents=50))

        def action(store, payload):
            store.set_language(payload)

        stats = benchmark_action(factory, action, "es", iterations=50)

        print(f"\nLarge state scoped diff: avg={stats['avg_us']:.0f}µs p99={stats['p99_us']:.0f}µs")
        assert stats["avg_us"] < 10000, f"Scoped diff too slow: {stats['avg_us']}µs"

    @pytest.mark.benchmark
    def test_large_state_full_diff(self) -> None:
        """Large state full diff (baseline for comparison)."""

        def factory():
            return BenchmarkStore(create_state(num_messages=100, num_documents=50))

        def action(store, payload):
            store.full_update(payload)  # Uses Action.scope.full_diff

        stats = benchmark_action(factory, action, "es", iterations=50)

        print(f"\nLarge state FULL diff: avg={stats['avg_us']:.0f}µs p99={stats['p99_us']:.0f}µs")
        # Full diff will be slower, just report it
        print(f"  (Full diff is expected to be slower than scoped diff)")

    @pytest.mark.benchmark
    def test_scoped_vs_full_diff_ratio(self) -> None:
        """Verify scoped diff is significantly faster than full diff."""

        def factory():
            return BenchmarkStore(create_state(num_messages=100, num_documents=50))

        def scoped_action(s: BenchmarkStore, p: str) -> None:
            s.set_language(p)

        def full_action(s: BenchmarkStore, p: str) -> None:
            s.full_update(p)

        scoped_stats = benchmark_action(factory, scoped_action, "es", iterations=50)  # type: ignore[arg-type]
        full_stats = benchmark_action(factory, full_action, "es", iterations=50)  # type: ignore[arg-type]

        ratio = full_stats["avg_us"] / scoped_stats["avg_us"]
        print(f"\nScoped: {scoped_stats['avg_us']:.0f}µs, Full: {full_stats['avg_us']:.0f}µs")
        print(f"Speedup ratio: {ratio:.1f}x")

        # Scoped should be at least 10x faster than full diff
        assert ratio > 10, f"Scoped diff not fast enough: only {ratio:.1f}x faster than full"


class TestPathCorrectness:
    """Verify paths are correct after the include_paths fix."""

    def test_scoped_diff_has_correct_path(self) -> None:
        """Scoped diff should produce paths relative to state root."""
        store = BenchmarkStore(create_state(num_messages=5, num_documents=2))
        received_deltas: list[Delta] = []
        store.subscribe(lambda d: received_deltas.append(d))

        store.set_language("es")

        assert len(received_deltas) == 1
        delta = received_deltas[0]
        flat_rows = list(delta.to_flat_rows())

        # Path should be ['language'], not [] (empty/relative)
        assert len(flat_rows) == 1
        assert flat_rows[0].path == ["language"], f"Expected ['language'], got {flat_rows[0].path}"
        assert flat_rows[0].value == "es"

    def test_nested_path_correctness(self) -> None:
        """Nested paths should be fully qualified."""

        @dataclass
        class NestedState:
            user: dict = field(default_factory=dict)

        class NestedStore(Store[NestedState]):
            @Store.action
            @staticmethod
            def set_setting(state: NestedState, value: str) -> frozenset[str]:
                state.user["settings"] = {"theme": value}
                return frozenset({"user"})

        store = NestedStore(NestedState(user={"settings": {"theme": "light"}}))
        received: list[Delta] = []
        store.subscribe(lambda d: received.append(d))

        store.set_setting("dark")

        assert len(received) == 1
        flat_rows = list(received[0].to_flat_rows())
        # Should have path starting with 'user'
        paths = [row.path for row in flat_rows]
        assert any("user" in str(p) for p in paths), f"Expected 'user' in paths, got {paths}"


if __name__ == "__main__":
    print("=" * 70)
    print("Store Diff Performance Benchmarks")
    print("=" * 70)

    # Run benchmarks directly
    test = TestDiffPerformance()
    test.test_small_state_scoped_diff()
    test.test_medium_state_scoped_diff()
    test.test_large_state_scoped_diff()
    test.test_large_state_full_diff()
    test.test_scoped_vs_full_diff_ratio()

    print("\n" + "=" * 70)
    print("Path Correctness Tests")
    print("=" * 70)
    path_test = TestPathCorrectness()
    path_test.test_scoped_diff_has_correct_path()
    print("\n✓ Scoped diff has correct path")
    path_test.test_nested_path_correctness()
    print("✓ Nested paths are correct")

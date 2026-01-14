"""Tests for the record_history pre-defined action."""

# pyright: reportPrivateUsage=false
# Tests need access to Store internals to verify behavior.

from __future__ import annotations

from agent_lib.agent.AgentRuntime import AgentRuntime
from agent_lib.context.components.LLMContext import LLMContext
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import NoProps
from agent_lib.store.Store import Store
from agent_lib.store.actions.record_history import record_history, RecordHistoryPayload


class MockLLMClient:
    """Mock LLM client for testing."""

    message_json_schema: str = "{}"

    def get_response(self, context: LLMContext) -> str:
        return '{"tool_calls": []}'


def mock_system_prompt() -> CtxComponent[NoProps]:
    """Create a mock system prompt component for testing."""
    return CtxComponent.leaf(lambda: "Test system prompt")


class StoreWithRecordHistory(Store):
    """Store subclass that includes the record_history action."""

    record_history = record_history


class TestRecordHistory:
    """Tests for the record_history action."""

    def test_record_history_appends_messages(self) -> None:
        """record_history appends messages to an agent's history."""
        store = StoreWithRecordHistory()
        runtime = AgentRuntime(store)
        runtime.create_agent("agent", MockLLMClient(), mock_system_prompt())

        store.record_history({
            "agent_name": "agent",
            "messages": [{"role": "user", "content": "Hello"}],
        })

        state = runtime.get_agent_state("agent")
        assert state is not None
        assert len(state.history) == 1
        assert state.history[0] == {"role": "user", "content": "Hello"}

    def test_record_history_multiple_messages(self) -> None:
        """record_history can append multiple messages at once."""
        store = StoreWithRecordHistory()
        runtime = AgentRuntime(store)
        runtime.create_agent("agent", MockLLMClient(), mock_system_prompt())

        store.record_history({
            "agent_name": "agent",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        })

        state = runtime.get_agent_state("agent")
        assert state is not None
        assert len(state.history) == 2
        assert state.history[0] == {"role": "user", "content": "Hello"}
        assert state.history[1] == {"role": "assistant", "content": "Hi there!"}

    def test_record_history_accumulates(self) -> None:
        """Multiple record_history calls accumulate messages."""
        store = StoreWithRecordHistory()
        runtime = AgentRuntime(store)
        runtime.create_agent("agent", MockLLMClient(), mock_system_prompt())

        store.record_history({
            "agent_name": "agent",
            "messages": [{"role": "user", "content": "First"}],
        })
        store.record_history({
            "agent_name": "agent",
            "messages": [{"role": "assistant", "content": "Second"}],
        })

        state = runtime.get_agent_state("agent")
        assert state is not None
        assert len(state.history) == 2
        assert state.history[0]["content"] == "First"
        assert state.history[1]["content"] == "Second"

    def test_record_history_different_agents(self) -> None:
        """record_history records to the correct agent."""
        store = StoreWithRecordHistory()
        runtime = AgentRuntime(store)
        runtime.create_agent("agent1", MockLLMClient(), mock_system_prompt())
        runtime.create_agent("agent2", MockLLMClient(), mock_system_prompt())

        store.record_history({
            "agent_name": "agent1",
            "messages": [{"role": "user", "content": "For agent1"}],
        })
        store.record_history({
            "agent_name": "agent2",
            "messages": [{"role": "user", "content": "For agent2"}],
        })

        state1 = runtime.get_agent_state("agent1")
        state2 = runtime.get_agent_state("agent2")

        assert state1 is not None
        assert state2 is not None
        assert len(state1.history) == 1
        assert len(state2.history) == 1
        assert state1.history[0]["content"] == "For agent1"
        assert state2.history[0]["content"] == "For agent2"

    def test_record_history_notifies_subscribers(self) -> None:
        """record_history triggers subscriber notifications."""
        store = StoreWithRecordHistory()
        runtime = AgentRuntime(store)
        runtime.create_agent("agent", MockLLMClient(), mock_system_prompt())

        notifications: list[bool] = []
        store.subscribe(lambda _affects: notifications.append(True))

        store.record_history({
            "agent_name": "agent",
            "messages": [{"role": "user", "content": "Hello"}],
        })

        assert len(notifications) == 1

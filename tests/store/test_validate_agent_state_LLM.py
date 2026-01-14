"""Tests for Store agent state validation via Agents.validate()."""

# pyright: reportPrivateUsage=false
# Tests need access to Store internals (_state) to verify behavior.

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agent_lib.agent.AgentState import AgentState
from agent_lib.store.State import State
from agent_lib.store.Store import Store


@dataclass
class PlannerState(AgentState):
    """Example agent state with extra fields."""

    plan: list[str] = field(default_factory=list)


@dataclass
class ExecutorState(AgentState):
    """Another example agent state."""

    task_count: int = 0


class TestValidateAgentStateSuccess:
    """Tests for valid agent_state configurations."""

    def test_valid_single_agent(self) -> None:
        """Single agent with matching key and agent_name passes."""

        class AppStore(Store):
            def __init__(self) -> None:
                self._state = State(
                    agent_state={
                        "planner": PlannerState(agent_name="planner"),
                    }
                )
                super().__init__()

        store = AppStore()
        assert store._state.agent_state["planner"].agent_name == "planner"

    def test_valid_multiple_agents(self) -> None:
        """Multiple agents with matching keys and agent_names pass."""

        class AppStore(Store):
            def __init__(self) -> None:
                self._state = State(
                    agent_state={
                        "planner": PlannerState(agent_name="planner"),
                        "executor": ExecutorState(agent_name="executor"),
                    }
                )
                super().__init__()

        store = AppStore()
        assert len(store._state.agent_state) == 2

    def test_no_agent_state(self) -> None:
        """Store with empty agent_state passes (no-op)."""

        class SimpleStore(Store):
            value: int

            def __init__(self) -> None:
                self.value = 0
                super().__init__()

        store = SimpleStore()
        assert store.value == 0
        assert store._state.agent_state == {}


class TestValidateAgentStateMismatch:
    """Tests for mismatched key/agent_name."""

    def test_key_mismatch_raises_value_error(self) -> None:
        """Mismatched key and agent_name raises ValueError."""

        class AppStore(Store):
            def __init__(self) -> None:
                self._state = State(
                    agent_state={
                        "wrong_key": PlannerState(agent_name="planner"),
                    }
                )
                super().__init__()

        with pytest.raises(ValueError, match="wrong_key.*planner"):
            AppStore()

    def test_one_mismatch_among_multiple(self) -> None:
        """One mismatched agent among valid ones raises ValueError."""

        class AppStore(Store):
            def __init__(self) -> None:
                self._state = State(
                    agent_state={
                        "planner": PlannerState(agent_name="planner"),
                        "wrong": ExecutorState(agent_name="executor"),
                    }
                )
                super().__init__()

        with pytest.raises(ValueError, match="wrong.*executor"):
            AppStore()


class TestValidateAgentStateTypeErrors:
    """Tests for type validation."""

    def test_non_agent_state_value_raises_type_error(self) -> None:
        """Value that is not AgentState raises TypeError."""

        class AppStore(Store):
            def __init__(self) -> None:
                self._state = State(
                    agent_state={
                        "planner": {"not": "an agent"},  # type: ignore[dict-item]
                    }
                )
                super().__init__()

        with pytest.raises(TypeError, match="must be an AgentState"):
            AppStore()

    def test_non_dict_agent_state_raises_type_error(self) -> None:
        """agent_state that is not a dict raises TypeError."""

        class AppStore(Store):
            def __init__(self) -> None:
                self._state = State()
                self._state.agent_state = [PlannerState(agent_name="planner")]  # type: ignore[assignment]
                super().__init__()

        with pytest.raises(TypeError, match="must be a dict"):
            AppStore()

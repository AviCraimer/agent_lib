"""Tests for Agent class."""

from __future__ import annotations

import pytest

from agent_lib.agent.Agent import Agent
from agent_lib.agent.Tool import Tool


class TestAgentCreation:
    """Tests for Agent initialization."""

    def test_create_agent(self) -> None:
        """Agent can be created with just a name."""
        agent = Agent(name="planner")

        assert agent.name == "planner"
        assert agent.tools == {}


class TestToolManagement:
    """Tests for granting and revoking tools."""

    def test_grant_tool(self) -> None:
        """Granting a tool makes it available."""
        agent = Agent(name="agent")
        tool = Tool(name="greet", description="Greet someone", json_schema="{}", handler=lambda x: f"Hello, {x}")

        agent.grant_tool(tool)

        assert agent.has_tool("greet")
        assert "greet" in agent.list_tools()

    def test_revoke_tool(self) -> None:
        """Revoking a tool removes it."""
        agent = Agent(name="agent")
        tool = Tool(name="greet", description="Greet someone", json_schema="{}", handler=lambda x: f"Hello, {x}")

        agent.grant_tool(tool)
        agent.revoke_tool("greet")

        assert not agent.has_tool("greet")

    def test_revoke_nonexistent_tool_raises(self) -> None:
        """Revoking a tool that isn't granted raises KeyError."""
        agent = Agent(name="agent")

        with pytest.raises(KeyError, match="not granted"):
            agent.revoke_tool("nonexistent")


class TestToolInvocation:
    """Tests for invoking tools."""

    def test_invoke_tool(self) -> None:
        """Invoking a tool calls its handler with the payload."""
        agent = Agent(name="agent")
        tool = Tool(name="double", description="Double a number", json_schema="{}", handler=lambda x: x * 2)  # pyright: ignore[reportUnknownLambdaType, reportOperatorIssue]

        agent.grant_tool(tool)
        result = agent.invoke("double", 21)

        assert result == 42

    def test_invoke_nonexistent_tool_raises(self) -> None:
        """Invoking a tool that isn't granted raises KeyError."""
        agent = Agent(name="agent")

        with pytest.raises(KeyError, match="not granted"):
            agent.invoke("nonexistent", "payload")

    def test_invoke_multiple_tools(self) -> None:
        """Agent can have and invoke multiple tools."""
        agent = Agent(name="agent")

        agent.grant_tool(Tool("add", "Add two numbers", "{}", lambda x: x[0] + x[1]))
        agent.grant_tool(Tool("multiply", "Multiply two numbers", "{}", lambda x: x[0] * x[1]))

        assert agent.invoke("add", (2, 3)) == 5
        assert agent.invoke("multiply", (2, 3)) == 6


class TestListTools:
    """Tests for listing tools."""

    def test_list_tools_empty(self) -> None:
        """New agent has no tools."""
        agent = Agent(name="agent")

        assert agent.list_tools() == []

    def test_list_tools_after_grants(self) -> None:
        """list_tools returns names of all granted tools."""
        agent = Agent(name="agent")

        agent.grant_tool(Tool("a", "Tool A", "{}", lambda x: x))
        agent.grant_tool(Tool("b", "Tool B", "{}", lambda x: x))
        agent.grant_tool(Tool("c", "Tool C", "{}", lambda x: x))

        tools = agent.list_tools()
        assert set(tools) == {"a", "b", "c"}

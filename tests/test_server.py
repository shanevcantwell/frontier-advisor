"""Tests for the MCP server tool definitions and handlers."""

import json
import pytest
import pytest_asyncio

from frontier_advisor.server import list_tools, call_tool


class TestListTools:
    @pytest.mark.asyncio
    async def test_returns_one_tool(self):
        tools = await list_tools()
        assert len(tools) == 1

    @pytest.mark.asyncio
    async def test_tool_name(self):
        tools = await list_tools()
        assert tools[0].name == "consult_advisor"

    @pytest.mark.asyncio
    async def test_required_fields(self):
        tools = await list_tools()
        schema = tools[0].inputSchema
        assert schema["required"] == ["question"]

    @pytest.mark.asyncio
    async def test_has_question_context_system_prompt(self):
        tools = await list_tools()
        props = tools[0].inputSchema["properties"]
        assert "question" in props
        assert "context" in props
        assert "system_prompt" in props

    @pytest.mark.asyncio
    async def test_no_tier_parameter(self):
        tools = await list_tools()
        props = tools[0].inputSchema["properties"]
        assert "tier" not in props


class TestCallTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await call_tool("nonexistent_tool", {})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "Unknown tool" in data["detail"]

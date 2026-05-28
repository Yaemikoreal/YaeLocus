"""Tests for Agent Loop module — tools, client, and agent_loop"""
import json
import pytest

from geocode.ai.tools import YAELOCUS_TOOLS, CMD_PATTERN, MAX_AGENT_ROUNDS
from geocode.ai.client import ToolCallAccumulator
from geocode.ai.agent_loop import _parse_error_from_result, AgentLoop


class TestYaelocusTools:
    def test_tools_structure(self):
        assert len(YAELOCUS_TOOLS) == 1
        tool = YAELOCUS_TOOLS[0]
        assert tool["type"] == "function"
        fn = tool["function"]
        assert fn["name"] == "execute_command"
        assert "command" in fn["parameters"]["properties"]
        assert fn["parameters"]["required"] == ["command"]

    def test_cmd_pattern(self):
        import re
        assert MAX_AGENT_ROUNDS == 4
        text = "some text\n[CMD]\ngeocode single test\n[/CMD]\nmore"
        matches = re.findall(CMD_PATTERN, text, re.DOTALL | re.IGNORECASE)
        assert len(matches) == 1
        assert "geocode single test" in matches[0]


class TestToolCallAccumulator:
    def test_single_tool_call(self):
        acc = ToolCallAccumulator()
        result = acc.update({
            "index": 0,
            "id": "call_123",
            "function": {"name": "execute_command", "arguments": '{"command": "config check"}'},
        })
        assert result["id"] == "call_123"
        assert result["name"] == "execute_command"
        assert "config check" in result["arguments"]

    def test_incremental_arguments(self):
        acc = ToolCallAccumulator()
        acc.update({
            "index": 0,
            "id": "call_456",
            "function": {"name": "execute_command", "arguments": '{"comm'},
        })
        result = acc.update({
            "index": 0,
            "function": {"arguments": 'and": "geocode single test"}'},
        })
        assert result["id"] == "call_456"
        assert "geocode" in result["arguments"]

    def test_reset(self):
        acc = ToolCallAccumulator()
        acc.update({"index": 0, "id": "call_1", "function": {"name": "test", "arguments": ""}})
        acc.reset()
        assert len(acc._calls) == 0


class TestParseErrorFromResult:
    def test_no_error(self):
        result = {"success": True, "stdout": "OK", "parsed": {"status": "ok"}}
        assert _parse_error_from_result(result) is None

    def test_json_error(self):
        result = {
            "success": False,
            "stdout": "",
            "stderr": "",
            "parsed": {"status": "error", "error": {"code": "NO_API_KEY", "message": "no key configured"}},
        }
        err = _parse_error_from_result(result)
        assert err is not None
        assert err["code"] == "NO_API_KEY"

    def test_stderr_error(self):
        result = {
            "success": False,
            "stdout": "",
            "stderr": "FILE_NOT_FOUND: file does not exist",
            "parsed": None,
        }
        err = _parse_error_from_result(result)
        assert err is not None
        assert err["code"] == "FILE_NOT_FOUND"

    def test_success_no_parsed(self):
        result = {"success": True, "stdout": "done", "parsed": None}
        assert _parse_error_from_result(result) is None


class TestAgentLoopImport:
    def test_import(self):
        from geocode.ai.agent_loop import AgentLoop
        assert AgentLoop is not None

    def test_cancel(self):
        from geocode.ai.agent_loop import AgentLoop
        loop = AgentLoop.__new__(AgentLoop)
        loop._cancelled = False
        loop.cancel()
        assert loop._cancelled is True
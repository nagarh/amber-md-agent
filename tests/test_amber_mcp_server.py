"""Smoke tests for amber_mcp_server — call functions directly, not via MCP protocol."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import amber_mcp_server as server


class TestConnectivity:
    def test_ping_returns_ok(self):
        result = server.ping()
        assert result["status"] == "ok"
        assert "message" in result

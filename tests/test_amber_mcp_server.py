"""Smoke tests for amber_mcp_server — call functions directly, not via MCP protocol."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import amber_mcp_server as server


class TestConnectivity:
    def test_ping_returns_ok(self):
        result = server.ping()
        assert result["status"] == "ok"
        assert isinstance(result.get("message"), str)
        assert result["message"]


class TestPDBTools:
    def test_fetch_pdb_empty_id_returns_error(self):
        result = server.fetch_pdb(pdb_id="", output_dir="/tmp")
        assert result["status"] == "error"
        assert result["tool"] == "fetch_pdb"

    def test_inspect_pdb_missing_file_returns_error(self):
        result = server.inspect_pdb(pdb_file="/nonexistent/file.pdb")
        assert result["status"] == "error"
        assert result["tool"] == "inspect_pdb"

    def test_clean_pdb_missing_file_returns_error(self):
        result = server.clean_pdb(pdb_file="/nonexistent/file.pdb")
        assert result["status"] == "error"
        assert result["tool"] == "clean_pdb"

    def test_preflight_missing_file_returns_error(self):
        result = server.preflight(pdb_file="/nonexistent/file.pdb")
        assert result["status"] == "error"
        assert result["tool"] == "preflight"

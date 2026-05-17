"""AmberMD Agent MCP Server — FastMCP wrapper over md_agent.py."""
import sys
from pathlib import Path
from typing import Annotated, Optional

from fastmcp import FastMCP
from pydantic import Field

sys.path.insert(0, str(Path(__file__).parent))
import md_agent

mcp = FastMCP("amber-md-agent")

# ─── Connectivity ─────────────────────────────────────────────────────────────

@mcp.tool()
def ping() -> dict:
    """Health check. Returns ok if server is running."""
    return {"status": "ok", "message": "amber-md-agent MCP server running"}


if __name__ == "__main__":
    mcp.run()

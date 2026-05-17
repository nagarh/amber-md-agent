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


# ─── PDB Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def fetch_pdb(
    pdb_id: Annotated[str, Field(description="4-character PDB ID e.g. '1IEP'")],
    output_dir: Annotated[str, Field(description="Directory to save .pdb file")] = ".",
) -> dict:
    """Fetch structure from RCSB PDB. Returns local file path."""
    try:
        if not pdb_id:
            raise ValueError("pdb_id cannot be empty")
        result = md_agent.fetch_pdb(pdb_id, output_dir)
        return {"status": "ok", "pdb_file": str(result), "pdb_id": pdb_id}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "fetch_pdb"}


@mcp.tool()
def inspect_pdb(
    pdb_file: Annotated[str, Field(description="Path to .pdb file to inspect")],
) -> dict:
    """Inspect PDB file — chains, residues, ligands, missing atoms, warnings."""
    try:
        result = md_agent.inspect_pdb(pdb_file)
        return {"status": "ok", "inspection": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "inspect_pdb"}


@mcp.tool()
def clean_pdb(
    pdb_file: Annotated[str, Field(description="Path to input .pdb file")],
    output_file: Annotated[Optional[str], Field(description="Output path. Defaults to clean.pdb in the same directory as input.")] = None,
    keep_waters: Annotated[bool, Field(description="Retain crystallographic waters")] = False,
    keep_hydrogens: Annotated[bool, Field(description="Retain existing hydrogens")] = False,
) -> dict:
    """Clean PDB — remove HETATM, waters, alt conformations. Returns cleaned file path."""
    try:
        result = md_agent.clean_pdb(pdb_file, output_file, keep_waters, keep_hydrogens)
        return {"status": "ok", "clean_pdb": str(result)}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "clean_pdb"}


@mcp.tool()
def preflight(
    pdb_file: Annotated[str, Field(description="Path to .pdb file for preflight check")],
    check_ligands: Annotated[bool, Field(description="Also check for unparametrized ligands")] = True,
) -> dict:
    """MANDATORY before system build. Checks for gaps, missing atoms, ligands, charge issues."""
    try:
        result = md_agent.preflight(pdb_file, check_ligands)
        return {"status": "ok", "preflight": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "preflight"}


if __name__ == "__main__":
    mcp.run()

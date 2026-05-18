# Tool-Calling Agent Design: amber-md-agent-v1

**Date:** 2026-05-17
**Branch:** `amber-md-agent-v1`
**Status:** Approved

## Goal

Replace Bash-invoked `python md_agent.py ...` commands with proper FastMCP tool calls inside Claude Code CLI. Improves agent behavior (structured I/O, parallel calls, typed params) and demonstrates production MCP architecture for portfolio.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Claude Code CLI                │
│   calls MCP tools (not Bash)                │
└────────────────┬────────────────────────────┘
                 │ FastMCP stdio transport
                 ▼
┌─────────────────────────────────────────────┐
│         amber_mcp_server.py                 │
│  FastMCP + Pydantic schemas                 │
│  ~40 tools, rich descriptions + validation  │
└────────────────┬────────────────────────────┘
                 │ Python import (not subprocess)
                 ▼
┌─────────────────────────────────────────────┐
│             md_agent.py                     │
│  Unchanged — all logic stays here           │
└────────────────┬────────────────────────────┘
                 │
                 ▼
         SLURM / HPC cluster
```

**Key decisions:**
- FastMCP via stdio transport — avoids socket hang risk seen with previous MCP servers on cluster
- `md_agent.py` untouched — zero regression risk, all existing logic preserved
- Pydantic models per tool — typed inputs, auto-validated, self-documenting
- Registered in `.mcp.json` at project root — Claude Code picks up automatically

## Components

### Single server file: `amber_mcp_server.py`

40 tools organized in 6 groups:

| Group | Tools |
|-------|-------|
| **PDB** | `fetch_pdb`, `inspect_pdb`, `clean_pdb`, `preflight` |
| **File Writers** | `write_mdin`, `write_tleap`, `write_cpptraj`, `write_groupfile`, `write_slurm`, `write_slurm_array` |
| **SLURM** | `submit_slurm`, `check_slurm_job`, `cancel_slurm_job`, `slurm_history` |
| **Validation** | `validate_step`, `validate_tleap`, `energy_parse`, `check_convergence` |
| **RAG** | `rag_query`, `rag_ingest`, `rag_section`, `rag_pages`, `rag_toc` |
| **Analysis** | `plot_timeseries`, `plot_bar`, `read_mdout`, `read_file_tail`, `read_file_head`, `list_files` |

### Pydantic schema pattern

Each tool has a dedicated Pydantic input model with typed fields and Field descriptions. Claude Code uses descriptions to populate arguments correctly without guessing.

```python
class FetchPDBInput(BaseModel):
    pdb_id: str = Field(..., description="4-character PDB ID e.g. '1IEP'")
    output_dir: Path = Field(Path("."), description="Directory to save .pdb file")

@mcp.tool()
def fetch_pdb(input: FetchPDBInput) -> dict:
    """Fetch structure from RCSB PDB. Returns local file path."""
    result = md_agent.fetch_pdb(input.pdb_id, str(input.output_dir))
    return {"status": "ok", "pdb_file": result, "pdb_id": input.pdb_id}
```

### `.mcp.json` registration

```json
{
  "mcpServers": {
    "amber": {
      "command": "/home/hn533621/.conda/envs/amber_development/bin/python",
      "args": ["amber_mcp_server.py"],
      "cwd": "/home/hn533621/Portfolio/amber-md-agent"
    }
  }
}
```

## Data Flow

```
Claude Code decides next action
    → calls tool with typed args (Pydantic validates before execution)
    → amber_mcp_server.py calls md_agent.py function
    → returns structured dict {"status": "ok", ...}
    → Claude reads result, decides next tool
```

### Error handling

Every tool wraps execution in try/except, returns structured error dict — never raw Python traceback:

```python
try:
    result = md_agent.fetch_pdb(...)
    return {"status": "ok", "pdb_file": result}
except Exception as e:
    return {"status": "error", "error": str(e), "tool": "fetch_pdb"}
```

Claude Code receives `{"status": "error", ...}` → triggers `amber-bugs.md` skill per CLAUDE.md rules.

### SLURM async pattern

SLURM operations remain inherently async — unchanged from current behavior:

1. `submit_slurm()` → returns `{"job_id": "12345", "status": "submitted"}`
2. Claude polls `check_slurm_job(job_id="12345")` after delay
3. `validate_step()` called when job finishes

## Testing

### Phase 1 — MCP connectivity gate

Single `ping()` tool deployed first. If Claude Code calls it without hanging, proceed to full 40-tool build. If FastMCP hangs on cluster, switch to custom stdio protocol (same pattern as `mcp_servers/pdb_server.py`) before building remaining tools.

### Phase 2 — Tool correctness smoke tests

Each group tested by direct Python call (not via MCP protocol):

```bash
python -c "
from amber_mcp_server import fetch_pdb, FetchPDBInput
result = fetch_pdb(FetchPDBInput(pdb_id='1IEP', output_dir='/tmp'))
assert result['status'] == 'ok'
print(result)
"
```

### Success criteria

- Claude Code calls `fetch_pdb` via MCP tool call — no Bash invocation
- Full alanine dipeptide minimization workflow runs via tools only — zero `python md_agent.py` in conversation transcript
- All tool returns are structured dicts — no text parsing required

## Out of Scope

- Rewriting `md_agent.py` logic
- Multiple MCP servers (one monolithic server only)
- Backwards-compatible Bash fallback (clean cut to MCP)
- Full test suite (smoke tests sufficient for experiment branch)

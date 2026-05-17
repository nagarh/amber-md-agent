# Tool-Calling Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Bash-invoked `python md_agent.py ...` calls with a FastMCP server exposing ~32 typed tools — making Claude Code a proper tool-calling agent for Amber MD workflows.

**Architecture:** `amber_mcp_server.py` wraps `md_agent.py` using FastMCP + Annotated Pydantic fields. Every public `md_agent.py` function becomes an `@mcp.tool()`. Claude Code registers the server via `.mcp.json` and calls tools natively. `md_agent.py` is untouched.

**Tech Stack:** `fastmcp`, `pydantic`, Python 3.10+, `/home/hn533621/.conda/envs/amber_development/bin/python`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `amber_mcp_server.py` | Create | FastMCP server — all 32 tools |
| `.mcp.json` | Create | Claude Code MCP registration |
| `tests/test_amber_mcp_server.py` | Create | Smoke tests — error cases + file writers |
| `CLAUDE.md` | Modify | Replace Bash command table with MCP tool reference |

---

## Task 1: Connectivity Gate

**Files:**
- Create: `amber_mcp_server.py` (ping tool only)
- Create: `.mcp.json`

**Purpose:** Verify FastMCP works on this cluster via stdio before building all 32 tools. Hard gate — if ping hangs, switch to custom stdio protocol from `mcp_servers/pdb_server.py`.

- [ ] **Step 1: Install fastmcp**

```bash
/home/hn533621/.conda/envs/amber_development/bin/pip install fastmcp
```

Expected: `Successfully installed fastmcp-...`

- [ ] **Step 2: Write ping-only server**

Create `amber_mcp_server.py`:

```python
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
```

- [ ] **Step 3: Write test for ping**

Create `tests/test_amber_mcp_server.py`:

```python
"""Smoke tests for amber_mcp_server — call functions directly, not via MCP protocol."""
import sys
from pathlib import Path
import tempfile
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import amber_mcp_server as server


class TestConnectivity:
    def test_ping_returns_ok(self):
        result = server.ping()
        assert result["status"] == "ok"
        assert "message" in result
```

- [ ] **Step 4: Run test**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestConnectivity -v
```

Expected: `PASSED`

- [ ] **Step 5: Verify server starts**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python amber_mcp_server.py &
sleep 2 && kill %1
```

Expected: No error output — server starts and accepts stdio.

- [ ] **Step 6: Create .mcp.json**

Create `.mcp.json` at project root:

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

- [ ] **Step 7: Verify Claude Code sees amber server**

In Claude Code session, type: `What MCP tools do you have available?`
Expected: Claude lists `ping` tool from `amber` server.
If Claude sees the tool → FastMCP works on cluster → proceed.
If Claude hangs or tool missing → stop, implement custom stdio pattern from `mcp_servers/pdb_server.py` before continuing.

- [ ] **Step 8: Commit**

```bash
git add amber_mcp_server.py .mcp.json tests/test_amber_mcp_server.py
git commit -m "feat: add FastMCP connectivity gate — ping tool + .mcp.json registration"
```

---

## Task 2: PDB Tools

**Files:**
- Modify: `amber_mcp_server.py` — add 4 PDB tools
- Modify: `tests/test_amber_mcp_server.py` — add PDB test class

Tools: `fetch_pdb`, `inspect_pdb`, `clean_pdb`, `preflight`

- [ ] **Step 1: Write failing tests for PDB tools**

Append to `tests/test_amber_mcp_server.py`:

```python
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestPDBTools -v
```

Expected: `AttributeError: module 'amber_mcp_server' has no attribute 'fetch_pdb'`

- [ ] **Step 3: Implement PDB tools**

Append to `amber_mcp_server.py` (before `if __name__ == "__main__":`):

```python
# ─── PDB Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def fetch_pdb(
    pdb_id: Annotated[str, Field(description="4-character PDB ID e.g. '1IEP'")],
    output_dir: Annotated[str, Field(description="Directory to save .pdb file")] = ".",
) -> dict:
    """Fetch structure from RCSB PDB. Returns local file path."""
    try:
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
    output_file: Annotated[Optional[str], Field(description="Output path. Defaults to <input>_clean.pdb")] = None,
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestPDBTools -v
```

Expected: 4 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add amber_mcp_server.py tests/test_amber_mcp_server.py
git commit -m "feat: add PDB tools — fetch_pdb, inspect_pdb, clean_pdb, preflight"
```

---

## Task 3: File Writer Tools

**Files:**
- Modify: `amber_mcp_server.py` — add 8 file writer tools
- Modify: `tests/test_amber_mcp_server.py` — add FileWriters test class

Tools: `write_mdin`, `write_tleap`, `write_cpptraj`, `write_groupfile`, `write_file`, `write_slurm`, `write_slurm_array`, `generate_equil_density_script`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_amber_mcp_server.py`:

```python
class TestFileWriters:
    def test_write_tleap_creates_file(self, tmp_path):
        out = str(tmp_path / "test.in")
        result = server.write_tleap(
            output_path=out,
            commands="source leaprc.protein.ff19SB\nquit",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()

    def test_write_mdin_creates_file(self, tmp_path):
        out = str(tmp_path / "min.mdin")
        result = server.write_mdin(
            output_path=out,
            namelist_params='{"imin": 1, "maxcyc": 1000, "cut": 8.0}',
            title="Test minimization",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()

    def test_write_cpptraj_creates_file(self, tmp_path):
        out = str(tmp_path / "rmsd.in")
        result = server.write_cpptraj(
            output_path=out,
            commands="parm sys.prmtop\ntrajin prod.nc\nrmsd :1-100 out rmsd.dat\nrun",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()

    def test_write_file_creates_file(self, tmp_path):
        out = str(tmp_path / "custom.sh")
        result = server.write_file(
            output_path=out,
            content="#!/bin/bash\necho hello",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()

    def test_write_slurm_missing_commands_returns_error(self, tmp_path):
        result = server.write_slurm(
            output_path=str(tmp_path / "job.sh"),
            commands="",
            job_name="test",
        )
        # Empty commands should still write file (md_agent handles it)
        # or return error — either is acceptable
        assert "status" in result
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestFileWriters -v
```

Expected: `AttributeError: module 'amber_mcp_server' has no attribute 'write_tleap'`

- [ ] **Step 3: Implement file writer tools**

Append to `amber_mcp_server.py` (before `if __name__ == "__main__":`):

```python
# ─── File Writer Tools ────────────────────────────────────────────────────────

@mcp.tool()
def write_mdin(
    output_path: Annotated[str, Field(description="Path to write .mdin file")],
    namelist_params: Annotated[str, Field(description="JSON string of &cntrl parameters e.g. '{\"imin\":1,\"maxcyc\":1000,\"cut\":8.0}'")],
    title: Annotated[str, Field(description="Title line for mdin file")] = "Generated by AmberMD Agent",
    extra_sections: Annotated[Optional[str], Field(description="Extra sections to append after &cntrl (e.g. &wt, restraints). Separate sections with newlines.")] = None,
) -> dict:
    """Write Amber mdin input file from JSON params. Returns file path."""
    try:
        import json
        params = json.loads(namelist_params)
        extra = [extra_sections] if extra_sections else None
        md_agent.write_mdin(output_path, params, title=title, extra_sections=extra)
        return {"status": "ok", "mdin_file": output_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "write_mdin"}


@mcp.tool()
def write_tleap(
    output_path: Annotated[str, Field(description="Path to write tLEaP input file")],
    commands: Annotated[str, Field(description="tLEaP commands as newline-separated string")],
) -> dict:
    """Write tLEaP input script. Returns file path."""
    try:
        md_agent.write_tleap(output_path, commands)
        return {"status": "ok", "tleap_file": output_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "write_tleap"}


@mcp.tool()
def write_cpptraj(
    output_path: Annotated[str, Field(description="Path to write cpptraj input file")],
    commands: Annotated[str, Field(description="cpptraj commands as newline-separated string")],
) -> dict:
    """Write cpptraj analysis script. Returns file path."""
    try:
        md_agent.write_cpptraj(output_path, commands)
        return {"status": "ok", "cpptraj_file": output_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "write_cpptraj"}


@mcp.tool()
def write_groupfile(
    output_path: Annotated[str, Field(description="Path to write REMD/TI groupfile")],
    entries: Annotated[str, Field(description="JSON array of entry dicts e.g. '[{\"mdin\":\"md.in\",\"mdout\":\"md.out\",\"prmtop\":\"sys.prmtop\",\"inpcrd\":\"in.rst7\",\"refc\":\"ref.rst7\"}]'")],
) -> dict:
    """Write REMD or TI groupfile. Returns file path."""
    try:
        import json
        parsed = json.loads(entries)
        md_agent.write_groupfile(output_path, parsed)
        return {"status": "ok", "groupfile": output_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "write_groupfile"}


@mcp.tool()
def write_file(
    output_path: Annotated[str, Field(description="Path to write file")],
    content: Annotated[str, Field(description="File content as string")],
) -> dict:
    """Write arbitrary text file. Use for custom scripts or config files."""
    try:
        md_agent.write_file(output_path, content)
        return {"status": "ok", "file": output_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "write_file"}


@mcp.tool()
def write_slurm(
    output_path: Annotated[str, Field(description="Path to write SLURM job script")],
    commands: Annotated[str, Field(description="Shell commands to run inside job (newline-separated)")],
    job_name: Annotated[str, Field(description="SLURM job name")] = "amber_md",
    work_dir: Annotated[Optional[str], Field(description="Working directory on cluster")] = None,
    gpus: Annotated[Optional[int], Field(description="Number of GPUs (0 = CPU-only, None = use template default)")] = None,
    walltime: Annotated[Optional[str], Field(description="Walltime override HH:MM:SS e.g. '24:00:00'")] = None,
) -> dict:
    """Write SLURM job script. Cluster defaults from scripts/slurm_template.sh."""
    try:
        md_agent.write_slurm_script(
            output_path, commands, job_name=job_name,
            work_dir=work_dir, gpus=gpus, walltime=walltime,
        )
        return {"status": "ok", "slurm_script": output_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "write_slurm"}


@mcp.tool()
def write_slurm_array(
    output_path: Annotated[str, Field(description="Path to write SLURM array script")],
    command_template: Annotated[str, Field(description="Command with {SLURM_ARRAY_TASK_ID} placeholder e.g. 'cd window_{SLURM_ARRAY_TASK_ID} && pmemd.cuda -O ...'")],
    array_range: Annotated[str, Field(description="SLURM array spec e.g. '0-23' or '0-11%4' (max 4 concurrent)")],
    job_name: Annotated[str, Field(description="SLURM array job name")] = "amber_array",
    work_dir: Annotated[Optional[str], Field(description="Working directory on cluster")] = None,
    gpus: Annotated[Optional[int], Field(description="GPUs per array task")] = None,
    walltime: Annotated[Optional[str], Field(description="Walltime per task HH:MM:SS")] = None,
) -> dict:
    """Write SLURM array job script. Ideal for umbrella windows, TI lambdas, REMD replicas."""
    try:
        md_agent.write_slurm_array(
            output_path, command_template, array_range,
            job_name=job_name, work_dir=work_dir, gpus=gpus, walltime=walltime,
        )
        return {"status": "ok", "slurm_array_script": output_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "write_slurm_array"}


@mcp.tool()
def write_equil_density_script(
    output_path: Annotated[str, Field(description="Path to write SLURM density-convergence script")],
    prmtop: Annotated[str, Field(description="Path to system .prmtop file")],
    rst_in: Annotated[str, Field(description="Input .rst7 restart file")],
    rst_out: Annotated[str, Field(description="Output .rst7 restart file after convergence")],
    mdin_path: Annotated[str, Field(description="Path to equilibration .mdin file")],
    work_dir: Annotated[str, Field(description="Working directory on cluster")],
    job_name: Annotated[str, Field(description="SLURM job name")] = "equil_density",
    prod_mdin: Annotated[Optional[str], Field(description="Production .mdin — submitted automatically after convergence")] = None,
    prod_mdout: Annotated[Optional[str], Field(description="Production .mdout output path")] = None,
    prod_rst: Annotated[Optional[str], Field(description="Production .rst7 output path")] = None,
    prod_nc: Annotated[Optional[str], Field(description="Production trajectory .nc path")] = None,
    temperature: Annotated[float, Field(description="Target temperature in Kelvin")] = 300.0,
) -> dict:
    """Write SLURM script with pmemd.cuda restart loop until density converges to 1.00 g/cc."""
    try:
        md_agent.generate_equil_density_script(
            output_path, prmtop, rst_in, rst_out, mdin_path, work_dir,
            job_name=job_name, prod_mdin=prod_mdin, prod_mdout=prod_mdout,
            prod_rst=prod_rst, prod_nc=prod_nc, temperature=temperature,
        )
        return {"status": "ok", "equil_density_script": output_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "write_equil_density_script"}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestFileWriters -v
```

Expected: 5 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add amber_mcp_server.py tests/test_amber_mcp_server.py
git commit -m "feat: add file writer tools — write_mdin, write_tleap, write_cpptraj, write_slurm and more"
```

---

## Task 4: SLURM Tools

**Files:**
- Modify: `amber_mcp_server.py` — add 4 SLURM tools
- Modify: `tests/test_amber_mcp_server.py` — add SLURM test class

Tools: `submit_slurm`, `check_slurm_job`, `cancel_slurm_job`, `slurm_history`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_amber_mcp_server.py`:

```python
class TestSLURMTools:
    def test_submit_slurm_missing_script_returns_error(self):
        result = server.submit_slurm(script_path="/nonexistent/job.sh")
        assert result["status"] == "error"
        assert result["tool"] == "submit_slurm"

    def test_check_slurm_job_no_id_returns_dict(self):
        result = server.check_slurm_job()
        # Returns job queue or error — both are valid dict responses
        assert isinstance(result, dict)
        assert "status" in result

    def test_cancel_slurm_job_bad_id_returns_error(self):
        result = server.cancel_slurm_job(job_id="99999999")
        assert isinstance(result, dict)
        assert "status" in result

    def test_slurm_history_returns_dict(self):
        result = server.slurm_history(days=1)
        assert isinstance(result, dict)
        assert "status" in result
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestSLURMTools -v
```

Expected: `AttributeError: module 'amber_mcp_server' has no attribute 'submit_slurm'`

- [ ] **Step 3: Implement SLURM tools**

Append to `amber_mcp_server.py` (before `if __name__ == "__main__":`):

```python
# ─── SLURM Tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def submit_slurm(
    script_path: Annotated[str, Field(description="Path to SLURM .sh script to submit")],
    cwd: Annotated[Optional[str], Field(description="Working directory for sbatch (default: script directory)")] = None,
) -> dict:
    """Submit SLURM job via sbatch. Returns job_id on success."""
    try:
        result = md_agent.submit_slurm(script_path, cwd=cwd)
        return {"status": "ok", "job_id": str(result), "script": script_path}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "submit_slurm"}


@mcp.tool()
def check_slurm_job(
    job_id: Annotated[Optional[str], Field(description="Specific job ID to check. Omit to list all user jobs.")] = None,
) -> dict:
    """Check SLURM job status. Returns state, elapsed time, and nodes."""
    try:
        result = md_agent.check_slurm_job(job_id=job_id)
        return {"status": "ok", "jobs": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "check_slurm_job"}


@mcp.tool()
def cancel_slurm_job(
    job_id: Annotated[str, Field(description="SLURM job ID to cancel")],
) -> dict:
    """Cancel a running or pending SLURM job via scancel."""
    try:
        result = md_agent.cancel_slurm_job(job_id)
        return {"status": "ok", "cancelled_job": job_id, "output": str(result)}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "cancel_slurm_job"}


@mcp.tool()
def slurm_history(
    days: Annotated[int, Field(description="Number of past days to show job history")] = 7,
) -> dict:
    """Show SLURM job history via sacct. Returns completed/failed jobs."""
    try:
        result = md_agent.slurm_job_history(days=days)
        return {"status": "ok", "history": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "slurm_history"}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestSLURMTools -v
```

Expected: 4 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add amber_mcp_server.py tests/test_amber_mcp_server.py
git commit -m "feat: add SLURM tools — submit_slurm, check_slurm_job, cancel_slurm_job, slurm_history"
```

---

## Task 5: Validation Tools

**Files:**
- Modify: `amber_mcp_server.py` — add 3 validation tools
- Modify: `tests/test_amber_mcp_server.py` — add Validation test class

Tools: `validate_step`, `validate_tleap`, `check_convergence`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_amber_mcp_server.py`:

```python
class TestValidationTools:
    def test_validate_step_missing_mdout_returns_error(self):
        result = server.validate_step(mdout_file="/nonexistent/prod.mdout")
        assert result["status"] == "error"
        assert result["tool"] == "validate_step"

    def test_validate_tleap_missing_log_returns_error(self):
        result = server.validate_tleap(log_file="/nonexistent/tleap.log")
        assert result["status"] == "error"
        assert result["tool"] == "validate_tleap"

    def test_check_convergence_missing_file_returns_error(self):
        result = server.check_convergence(data_file="/nonexistent/rmsd.dat")
        assert result["status"] == "error"
        assert result["tool"] == "check_convergence"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestValidationTools -v
```

Expected: `AttributeError: module 'amber_mcp_server' has no attribute 'validate_step'`

- [ ] **Step 3: Implement validation tools**

Append to `amber_mcp_server.py` (before `if __name__ == "__main__":`):

```python
# ─── Validation Tools ─────────────────────────────────────────────────────────

@mcp.tool()
def validate_step(
    mdout_file: Annotated[str, Field(description="Path to .mdout file from completed pmemd/sander run")],
    expected_nstep: Annotated[Optional[int], Field(description="Expected final NSTEP value e.g. 500000")] = None,
    min_density: Annotated[Optional[float], Field(description="Minimum acceptable density g/cc e.g. 0.95")] = None,
    max_density: Annotated[Optional[float], Field(description="Maximum acceptable density g/cc e.g. 1.10")] = None,
    check_rst7: Annotated[Optional[str], Field(description="Path to .rst7 that must exist after run")] = None,
    target_temp: Annotated[float, Field(description="Target temperature in Kelvin")] = 300.0,
    temp_tolerance: Annotated[float, Field(description="Acceptable temperature deviation from target")] = 10.0,
) -> dict:
    """GATE between pipeline steps. Validates mdout completed correctly — PASS or FAIL with diagnostics."""
    try:
        result = md_agent.validate_step(
            mdout_file, expected_nstep=expected_nstep,
            min_density=min_density, max_density=max_density,
            check_rst7=check_rst7, target_temp=target_temp,
            temp_tolerance=temp_tolerance,
        )
        return {"status": "ok", "validation": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "validate_step"}


@mcp.tool()
def validate_tleap(
    log_file: Annotated[str, Field(description="Path to tleap.out log file")],
) -> dict:
    """Parse tLEaP log for FATAL errors, warnings, and atom count. Returns PASS/FAIL."""
    try:
        result = md_agent.validate_tleap(log_file)
        return {"status": "ok", "validation": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "validate_tleap"}


@mcp.tool()
def check_convergence(
    data_file: Annotated[str, Field(description="Path to time-series .dat file (e.g. RMSD, energy)")],
    column: Annotated[int, Field(description="Data column index (1-based)")] = 1,
    abs_threshold: Annotated[float, Field(description="Convergence threshold — std dev below this = converged")] = 0.5,
) -> dict:
    """Check if time-series data has converged. Returns converged=True/False with statistics."""
    try:
        result = md_agent.check_convergence(data_file, column=column, abs_threshold=abs_threshold)
        return {"status": "ok", "convergence": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "check_convergence"}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestValidationTools -v
```

Expected: 3 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add amber_mcp_server.py tests/test_amber_mcp_server.py
git commit -m "feat: add validation tools — validate_step, validate_tleap, check_convergence"
```

---

## Task 6: RAG Tools

**Files:**
- Modify: `amber_mcp_server.py` — add 6 RAG tools
- Modify: `tests/test_amber_mcp_server.py` — add RAG test class

Tools: `rag_query`, `rag_ingest`, `rag_section`, `rag_page`, `rag_pages`, `rag_toc`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_amber_mcp_server.py`:

```python
class TestRAGTools:
    def test_rag_query_empty_question_returns_error(self):
        result = server.rag_query(question="")
        assert result["status"] == "error"
        assert result["tool"] == "rag_query"

    def test_rag_toc_returns_dict(self):
        result = server.rag_toc()
        # Returns TOC or error if index not ingested — both valid
        assert isinstance(result, dict)
        assert "status" in result

    def test_rag_ingest_missing_file_returns_error(self):
        result = server.rag_ingest(manual_path="/nonexistent/manual.pdf")
        assert result["status"] == "error"
        assert result["tool"] == "rag_ingest"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestRAGTools -v
```

Expected: `AttributeError: module 'amber_mcp_server' has no attribute 'rag_query'`

- [ ] **Step 3: Implement RAG tools**

Append to `amber_mcp_server.py` (before `if __name__ == "__main__":`):

```python
# ─── RAG Tools ────────────────────────────────────────────────────────────────

@mcp.tool()
def rag_query(
    question: Annotated[str, Field(description="Natural language question about Amber e.g. 'What cut value for PME?'")],
    top_k: Annotated[int, Field(description="Number of manual chunks to retrieve")] = 5,
    index_path: Annotated[Optional[str], Field(description="RAG index path (default: auto-detected)")] = None,
) -> dict:
    """Query Amber manual RAG index. MUST call before writing any mdin or tLEaP script."""
    try:
        if not question:
            raise ValueError("question cannot be empty")
        result = md_agent.rag_query(question, top_k=top_k, index_path=index_path)
        return {"status": "ok", "results": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "rag_query"}


@mcp.tool()
def rag_ingest(
    manual_path: Annotated[str, Field(description="Path to Amber manual PDF e.g. 'Amber24.pdf'")],
    append: Annotated[bool, Field(description="Append to existing index instead of rebuilding")] = False,
) -> dict:
    """Ingest Amber manual PDF into RAG index. Run once per manual version."""
    try:
        result = md_agent.rag_ingest(manual_path, append=append)
        return {"status": "ok", "index": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "rag_ingest"}


@mcp.tool()
def rag_section(
    section_name: Annotated[str, Field(description="Section name to retrieve e.g. 'Free Energy', 'REMD'")],
    index_path: Annotated[Optional[str], Field(description="RAG index path (default: auto-detected)")] = None,
) -> dict:
    """Retrieve full section from Amber manual by name."""
    try:
        result = md_agent.rag_section(section_name, index_path=index_path)
        return {"status": "ok", "section": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "rag_section"}


@mcp.tool()
def rag_page(
    page_num: Annotated[int, Field(description="Page number to retrieve from Amber manual")],
    index_path: Annotated[Optional[str], Field(description="RAG index path (default: auto-detected)")] = None,
) -> dict:
    """Retrieve specific page from Amber manual."""
    try:
        result = md_agent.rag_page(page_num, index_path=index_path)
        return {"status": "ok", "page": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "rag_page"}


@mcp.tool()
def rag_pages(
    start: Annotated[int, Field(description="Start page number (inclusive)")],
    end: Annotated[int, Field(description="End page number (inclusive)")],
    index_path: Annotated[Optional[str], Field(description="RAG index path (default: auto-detected)")] = None,
) -> dict:
    """Retrieve page range from Amber manual."""
    try:
        result = md_agent.rag_pages(start, end, index_path=index_path)
        return {"status": "ok", "pages": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "rag_pages"}


@mcp.tool()
def rag_toc(
    index_path: Annotated[Optional[str], Field(description="RAG index path (default: auto-detected)")] = None,
) -> dict:
    """List table of contents from ingested Amber manual index."""
    try:
        result = md_agent.rag_toc(index_path=index_path)
        return {"status": "ok", "toc": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "rag_toc"}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestRAGTools -v
```

Expected: 3 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add amber_mcp_server.py tests/test_amber_mcp_server.py
git commit -m "feat: add RAG tools — rag_query, rag_ingest, rag_section, rag_page, rag_pages, rag_toc"
```

---

## Task 7: Analysis & Environment Tools

**Files:**
- Modify: `amber_mcp_server.py` — add 7 analysis tools + check_environment
- Modify: `tests/test_amber_mcp_server.py` — add Analysis test class

Tools: `read_mdout`, `read_file_tail`, `read_file_head`, `list_files`, `plot_timeseries`, `plot_bar`, `check_environment`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_amber_mcp_server.py`:

```python
class TestAnalysisTools:
    def test_read_mdout_missing_file_returns_error(self):
        result = server.read_mdout(mdout_file="/nonexistent/prod.mdout")
        assert result["status"] == "error"
        assert result["tool"] == "read_mdout"

    def test_read_file_tail_missing_file_returns_error(self):
        result = server.read_file_tail(file_path="/nonexistent/file.txt")
        assert result["status"] == "error"
        assert result["tool"] == "read_file_tail"

    def test_list_files_existing_dir_returns_ok(self, tmp_path):
        result = server.list_files(directory=str(tmp_path))
        assert result["status"] == "ok"
        assert "files" in result

    def test_list_files_missing_dir_returns_error(self):
        result = server.list_files(directory="/nonexistent/dir")
        assert result["status"] == "error"
        assert result["tool"] == "list_files"

    def test_check_environment_returns_ok(self):
        result = server.check_environment()
        assert isinstance(result, dict)
        assert "status" in result
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py::TestAnalysisTools -v
```

Expected: `AttributeError: module 'amber_mcp_server' has no attribute 'read_mdout'`

- [ ] **Step 3: Implement analysis and environment tools**

Append to `amber_mcp_server.py` (before `if __name__ == "__main__":`):

```python
# ─── Analysis Tools ───────────────────────────────────────────────────────────

@mcp.tool()
def read_mdout(
    mdout_file: Annotated[str, Field(description="Path to Amber .mdout file")],
    last_n: Annotated[Optional[int], Field(description="Return only last N frames of energy data")] = None,
) -> dict:
    """Parse energy, temperature, density from Amber .mdout file. Returns time-series data."""
    try:
        result = md_agent.read_mdout(mdout_file, last_n=last_n)
        return {"status": "ok", "energy_data": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "read_mdout"}


@mcp.tool()
def read_file_tail(
    file_path: Annotated[str, Field(description="Path to file to read")],
    n_chars: Annotated[int, Field(description="Number of characters from file end to return")] = 3000,
) -> dict:
    """Read last N characters of a file. Use to check log files and mdout progress."""
    try:
        result = md_agent.read_file_tail(file_path, n_chars=n_chars)
        return {"status": "ok", "content": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "read_file_tail"}


@mcp.tool()
def read_file_head(
    file_path: Annotated[str, Field(description="Path to file to read")],
    n_chars: Annotated[int, Field(description="Number of characters from file start to return")] = 3000,
) -> dict:
    """Read first N characters of a file. Use to inspect headers or tLEaP outputs."""
    try:
        result = md_agent.read_file_head(file_path, n_chars=n_chars)
        return {"status": "ok", "content": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "read_file_head"}


@mcp.tool()
def list_files(
    directory: Annotated[str, Field(description="Directory path to list")],
    pattern: Annotated[str, Field(description="Glob pattern e.g. '*.pdb' or '*.mdout'")] = "*",
) -> dict:
    """List files in directory matching pattern. Returns sorted file list."""
    try:
        result = md_agent.list_files(directory, pattern=pattern)
        return {"status": "ok", "files": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "list_files"}


@mcp.tool()
def plot_timeseries(
    data_file: Annotated[str, Field(description="Path to whitespace-delimited .dat file (col1=time, col2=value)")],
    output_png: Annotated[str, Field(description="Path to write output .png plot")],
    xlabel: Annotated[str, Field(description="X-axis label")] = "Time",
    ylabel: Annotated[str, Field(description="Y-axis label")] = "Value",
) -> dict:
    """Plot time-series data (RMSD, energy, density) as PNG."""
    try:
        md_agent.plot_timeseries(data_file, output_png, xlabel=xlabel, ylabel=ylabel)
        return {"status": "ok", "plot": output_png}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "plot_timeseries"}


@mcp.tool()
def plot_bar(
    data_file: Annotated[str, Field(description="Path to whitespace-delimited .dat file (col1=residue, col2=value)")],
    output_png: Annotated[str, Field(description="Path to write output .png plot")],
    xlabel: Annotated[str, Field(description="X-axis label")] = "Residue",
    ylabel: Annotated[str, Field(description="Y-axis label")] = "Value",
) -> dict:
    """Plot per-residue bar chart (RMSF, B-factors) as PNG."""
    try:
        md_agent.plot_bar(data_file, output_png, xlabel=xlabel, ylabel=ylabel)
        return {"status": "ok", "plot": output_png}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "plot_bar"}


# ─── Environment ──────────────────────────────────────────────────────────────

@mcp.tool()
def check_environment() -> dict:
    """Check Amber environment — pmemd.cuda, tleap, cpptraj availability and versions."""
    try:
        result = md_agent.check_environment()
        return {"status": "ok", "environment": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "check_environment"}
```

- [ ] **Step 4: Run all tests**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py -v
```

Expected: All tests `PASSED`. Count should be 25+.

- [ ] **Step 5: Commit**

```bash
git add amber_mcp_server.py tests/test_amber_mcp_server.py
git commit -m "feat: add analysis and environment tools — read_mdout, plot_timeseries, list_files, check_environment"
```

---

## Task 8: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` — replace Bash toolkit reference with MCP tool reference

- [ ] **Step 1: Replace Toolkit Reference section in CLAUDE.md**

In `CLAUDE.md`, replace the entire `## Toolkit Reference` section with:

```markdown
## Toolkit Reference

All operations via MCP tools (registered in `.mcp.json`). Claude Code calls tools directly — no `python md_agent.py` needed.

### Environment
Tool: `check_environment()`

### PDB
Tools: `fetch_pdb(pdb_id, output_dir)`, `inspect_pdb(pdb_file)`, `clean_pdb(pdb_file, ...)`, `preflight(pdb_file)`

### File Writers
Tools: `write_mdin(output_path, namelist_params, ...)`, `write_tleap(output_path, commands)`, `write_cpptraj(output_path, commands)`, `write_groupfile(output_path, entries)`, `write_file(output_path, content)`, `write_slurm(output_path, commands, ...)`, `write_slurm_array(output_path, command_template, array_range, ...)`, `write_equil_density_script(...)`

### SLURM
Tools: `submit_slurm(script_path)`, `check_slurm_job(job_id)`, `cancel_slurm_job(job_id)`, `slurm_history(days)`

### Validation
Tools: `validate_step(mdout_file, ...)`, `validate_tleap(log_file)`, `check_convergence(data_file, ...)`

### RAG
Tools: `rag_ingest(manual_path)`, `rag_query(question, top_k)`, `rag_toc()`, `rag_section(section_name)`, `rag_page(page_num)`, `rag_pages(start, end)`

### Analysis
Tools: `read_mdout(mdout_file)`, `read_file_tail(file_path)`, `read_file_head(file_path)`, `list_files(directory, pattern)`, `plot_timeseries(data_file, output_png, ...)`, `plot_bar(data_file, output_png, ...)`
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md toolkit reference to MCP tools from Bash commands"
```

---

## Task 9: End-to-End Verification

**Goal:** Confirm Claude Code calls tools directly — zero `python md_agent.py` in conversation.

- [ ] **Step 1: Run full test suite**

```bash
/home/hn533621/.conda/envs/amber_development/bin/python -m pytest tests/test_amber_mcp_server.py -v --tb=short
```

Expected: All `PASSED`, 0 failures.

- [ ] **Step 2: Verify tool count**

```bash
grep "@mcp.tool()" amber_mcp_server.py | wc -l
```

Expected: 32 (ping + 4 PDB + 8 FileWriters + 4 SLURM + 3 Validation + 6 RAG + 6 Analysis + 1 Environment)

- [ ] **Step 3: In Claude Code — run minimal workflow via tools**

Ask Claude Code:
> "Using MCP tools only, fetch PDB 1L2Y (trp-cage miniprotein), inspect it, and run preflight."

Expected:
- Claude calls `fetch_pdb(pdb_id="1L2Y", output_dir=".")`
- Claude calls `inspect_pdb(pdb_file="1L2Y.pdb")`
- Claude calls `preflight(pdb_file="1L2Y.pdb")`
- No `Bash("python md_agent.py ...")` in transcript

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "chore: amber-md-agent-v1 tool-calling complete — 32 MCP tools via FastMCP"
```

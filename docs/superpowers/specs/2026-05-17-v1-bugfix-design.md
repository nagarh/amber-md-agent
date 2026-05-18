# Design: amber-md-agent v1 Surgical Patches

Date: 2026-05-17
Branch: amber-md-agent-v1
Status: Approved

## Scope

Three surgical fixes to bring v1 to parity with main and close bugs exposed by the trpcage 1L2Y 1ns stress test. No new features beyond the three patches below.

---

## Patch 1 — validate_step temperature false-WARN

### Problem

`md_agent.py` ~line 1505:

```python
temp_matches = re.findall(r'TEMP\(K\)\s+=\s+([\d.]+)', content)
```

Regex runs on full mdout content. Production mdout contains three `TEMP(K) =` occurrences:
- Time-series NSTEP lines (correct, e.g. 290–300 K)
- `A V E R A G E S` block: `TEMP(K) = 300.01`
- `RMS FLUCTUATIONS` block: `TEMP(K) = 3.25`

`late_temps = temps[int(len(temps)*0.8):]` then averages the tail, which may include the 3.25K RMS FLUCT value, pulling `avg_temp` below the 10K WARN threshold. Stress test: false WARN at 290K for a run with true average 300.01K.

### Fix

Before the regex, find the AVERAGES section start and truncate:

```python
avg_idx = content.find('  A V E R A G E S')
ts_content = content[:avg_idx] if avg_idx > 0 else content
temp_matches = re.findall(r'TEMP\(K\)\s+=\s+([\d.]+)', ts_content)
```

Identical truncation pattern already used by burst density `parse_density` helper (confirmed in stress test `run_burst.sh`). Only time-series NSTEP temperatures remain.

**File**: `md_agent.py`, `validate_step()` ~line 1505
**Change**: 3 lines (add avg_idx, ts_content; change `content` → `ts_content` in findall)

---

## Patch 2 — (confirmed no-op)

`write_equil_density_script` / `generate_equil_density_script` already auto-creates `equil_density_burst.mdin` at lines 1707–1724 in v1. Stress test gap was procedural (wrong mdin_path argument), not a code bug. No code change needed.

---

## Patch 3 — run_tleap + run_cpptraj MCP tools

### Problem

v1 `amber_mcp_server.py` exposes `write_tleap`/`write_cpptraj` (write input file) and `submit_slurm` (submit job) but no direct-exec path. For tiny system-prep jobs (tLEaP <5s, small cpptraj analysis <10s), the agent must write a SLURM script, submit, poll, and read output — 4 round-trips for a job that runs in seconds. Main branch has `run_tleap()` and `run_cpptraj()` in `md_agent.py` but they are not exposed as MCP tools in v1.

### Fix

Add two MCP tools in `amber_mcp_server.py` that wrap the existing `md_agent.run_tleap()` and `md_agent.run_cpptraj()` functions:

```python
@mcp.tool()
def run_tleap(
    input_file: Annotated[str, Field(description="Path to tLEaP input (.in) file")],
    cwd: Annotated[Optional[str], Field(description="Working directory")] = None,
) -> dict:
    """Run tLEaP directly (login-node, tiny jobs only). Returns stdout, stderr, leap_log."""
    try:
        result = md_agent.run_tleap(input_file, cwd=cwd)
        return {"status": "ok" if result["success"] else "error", **result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "run_tleap"}


@mcp.tool()
def run_cpptraj(
    input_file: Annotated[str, Field(description="Path to cpptraj input (.in) file")],
    cwd: Annotated[Optional[str], Field(description="Working directory")] = None,
) -> dict:
    """Run cpptraj directly (login-node, tiny jobs only). Returns stdout, stderr."""
    try:
        result = md_agent.run_cpptraj(input_file, cwd=cwd)
        return {"status": "ok" if result["success"] else "error", **result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "run_cpptraj"}
```

**Constraint**: Amber must be loaded in the MCP server process environment (`source /opt/shared/apps/amber/24/amber.sh`). If not, both tools return `error: tleap: command not found` immediately — agent falls back to SLURM path.

**CLAUDE.md update**: Add note that `run_tleap` and `run_cpptraj` are login-node exceptions for <30s tiny jobs. All pmemd/sander/antechamber remain SLURM-only without exception.

**File**: `amber_mcp_server.py` — add two `@mcp.tool()` functions after `write_equil_density_script` section

---

## Tests

- `test_validate_step_temp_averages_excluded`: mock mdout with AVERAGES block; assert no false WARN
- `test_run_tleap_success`: mock subprocess; assert status=ok + leap_log returned
- `test_run_tleap_not_found`: mock `tleap: command not found`; assert status=error
- `test_run_cpptraj_success`: mock subprocess; assert status=ok
- `test_run_cpptraj_fail`: non-zero exit; assert status=error

All tests in `tests/test_amber_mcp_server.py`.

---

## CLAUDE.md Changes

In the "What runs where" section, add under login-node:
> Exception: `run_tleap` and `run_cpptraj` MCP tools may run on login node for tiny (<30s) jobs. If Amber not in PATH, fall back to write_tleap/write_slurm/submit_slurm.

---

## Summary

| Patch | File | Lines changed |
|-------|------|---------------|
| 1: validate_step temp fix | `md_agent.py` | ~3 |
| 2: burst mdin (no-op) | — | 0 |
| 3a: run_tleap MCP tool | `amber_mcp_server.py` | ~12 |
| 3b: run_cpptraj MCP tool | `amber_mcp_server.py` | ~12 |
| 3c: CLAUDE.md exception note | `CLAUDE.md` | ~2 |
| New tests | `tests/test_amber_mcp_server.py` | ~50 |

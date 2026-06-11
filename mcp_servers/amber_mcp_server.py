"""AmberMD Agent MCP Server — FastMCP wrapper over md_agent.py."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Annotated, Optional

from fastmcp import FastMCP
from pydantic import Field

# Make scripts/ and mcp_servers/ importable for sibling helpers
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import md_agent

# Canonical interpreter + tool binaries — resolved once at import time
PYTHON_BIN = "/home/hn533621/.conda/envs/amber_development/bin/python"
PROPKA_BIN = shutil.which("propka3") or "/home/hn533621/.conda/envs/amber_development/bin/propka3"

mcp = FastMCP("amber-md-agent")


def _ensure_ter_records(pdb_path: str) -> None:
    """Insert TER cards at chain boundaries if missing (CRIT-04 fix).

    MDAnalysis mda.Merge (used by add_caps.py) and some other tools drop TER
    records on write.  Without TER cards tLEaP merges all chains into one residue
    sequence, breaking multi-chain topology.
    """
    lines = Path(pdb_path).read_text().splitlines(keepends=True)
    out: list = []
    prev_chain: str | None = None
    for line in lines:
        if line.startswith(("ATOM", "HETATM")):
            cur_chain = line[21]
            if prev_chain is not None and cur_chain != prev_chain:
                # Only insert if previous line is not already a TER
                if not out or not out[-1].startswith("TER"):
                    out.append("TER\n")
            prev_chain = cur_chain
        elif line.startswith("TER"):
            prev_chain = None  # reset — explicit TER already present
        out.append(line)
    # Append final TER before END if last coord line has no trailing TER
    if prev_chain is not None and (not out or not out[-1].startswith("TER")):
        out.append("TER\n")
    Path(pdb_path).write_text("".join(out))


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


# ─── File Writer Tools ────────────────────────────────────────────────────────────

@mcp.tool()
def write_mdin(
    output_path: Annotated[str, Field(description="Path to write .mdin file")],
    namelist_params: Annotated[str, Field(description="JSON string of &cntrl parameters e.g. '{\"imin\":1,\"maxcyc\":1000,\"cut\":8.0}'")],
    title: Annotated[str, Field(description="Title line for mdin file")] = "Generated by AmberMD Agent",
    extra_sections: Annotated[Optional[str], Field(description="Extra sections to append after &cntrl (e.g. &wt, restraints)")] = None,
) -> dict:
    """Write Amber mdin input file from JSON params. Returns file path."""
    try:
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
    entries: Annotated[str, Field(description="JSON array of entry dicts e.g. '[{\"mdin\":\"md.in\",\"mdout\":\"md.out\",\"prmtop\":\"sys.prmtop\",\"inpcrd\":\"in.rst7\"}]'")],
) -> dict:
    """Write REMD or TI groupfile. Returns file path."""
    try:
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
    mdin_path: Annotated[str, Field(description="Path to equilibration .mdin file or its parent directory")],
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


# ─── Direct Exec Tools (login-node, tiny jobs only) ──────────────────────────

@mcp.tool()
def run_tleap(
    input_file: Annotated[str, Field(description="Path to tLEaP input (.in) file")],
    cwd: Annotated[Optional[str], Field(description="Working directory")] = None,
) -> dict:
    """Run tLEaP directly on login node (tiny jobs <30s only). Returns stdout, stderr, leap_log.
    Requires Amber in PATH. Falls back to write_tleap + write_slurm + submit_slurm for heavy jobs."""
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
    """Run cpptraj directly on login node (tiny jobs <30s only). Returns stdout, stderr.
    Requires Amber in PATH. Falls back to write_cpptraj + write_slurm + submit_slurm for heavy jobs."""
    try:
        result = md_agent.run_cpptraj(input_file, cwd=cwd)
        return {"status": "ok" if result["success"] else "error", **result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "run_cpptraj"}


# ─── SLURM Tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def submit_slurm(
    script_path: Annotated[str, Field(description="Path to SLURM .sh script to submit")],
    cwd: Annotated[Optional[str], Field(description="Working directory for sbatch (default: script directory)")] = None,
) -> dict:
    """Submit SLURM job via sbatch. Returns job_id on success."""
    try:
        result = md_agent.submit_slurm(script_path, cwd=cwd)
        if isinstance(result, dict) and not result.get("success"):
            return {"status": "error", "error": result.get("stderr", "Unknown error"), "tool": "submit_slurm"}
        job_id = result if isinstance(result, str) else result.get("job_id", str(result))
        return {"status": "ok", "job_id": str(job_id), "script": script_path}
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
def wait_for_slurm_job(
    job_id: Annotated[str, Field(description="SLURM job ID to wait for")],
    poll_interval: Annotated[int, Field(description="Seconds between polls. Use 5 for short CPU prep jobs (tLEaP, antechamber). Use 30-60 for GPU MD runs.")] = 5,
    timeout: Annotated[int, Field(description="Max seconds to wait before returning TIMEOUT")] = 3600,
) -> dict:
    """Block until SLURM job completes — polls internally, no LLM round-trip per check.

    Use this instead of check_slurm_job loop for all prep steps (tLEaP, antechamber,
    pdb4amber). Returns final state (COMPLETED/FAILED/TIMEOUT) + elapsed seconds.

    Example: submit_slurm(...) → wait_for_slurm_job(job_id, poll_interval=5) → validate_tleap(...)
    """
    try:
        result = md_agent.wait_for_slurm_job(job_id, poll_interval=poll_interval, timeout=timeout)
        ok = result["state"] == "COMPLETED"
        return {"status": "ok" if ok else "error",
                "state": result["state"],
                "elapsed_s": result["elapsed_s"],
                "job_id": job_id,
                "tool": "wait_for_slurm_job"}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "wait_for_slurm_job"}


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
        if result.get("status") == "error":
            return {"status": "error", "error": result.get("error", "Unknown error"), "tool": "check_convergence"}
        return {"status": "ok", "convergence": result}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "check_convergence"}


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
        if "error" in result:
            return {"status": "error", "error": result["error"], "tool": "read_file_tail"}
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
        if "error" in result:
            return {"status": "error", "error": result["error"], "tool": "read_file_head"}
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
        if not Path(directory).exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
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
    title: Annotated[Optional[str], Field(description="Plot title")] = None,
    column_x: Annotated[int, Field(description="Column index for X data (0-based)")] = 0,
    column_y: Annotated[int, Field(description="Column index for Y data (0-based)")] = 1,
    time_scale: Annotated[float, Field(description="Scale factor for time axis")] = 1.0,
) -> dict:
    """Plot time-series data (RMSD, energy, density) as PNG."""
    try:
        result = md_agent.plot_timeseries(data_file, output_png, xlabel=xlabel, ylabel=ylabel, title=title, column_x=column_x, column_y=column_y, time_scale=time_scale)
        if isinstance(result, dict) and not result.get("success", True):
            return {"status": "error", "error": result.get("error", "plot failed"), "tool": "plot_timeseries"}
        return {"status": "ok", "plot": output_png}
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "plot_timeseries"}


@mcp.tool()
def plot_bar(
    data_file: Annotated[str, Field(description="Path to whitespace-delimited .dat file (col1=residue, col2=value)")],
    output_png: Annotated[str, Field(description="Path to write output .png plot")],
    xlabel: Annotated[str, Field(description="X-axis label")] = "Residue",
    ylabel: Annotated[str, Field(description="Y-axis label")] = "Value",
    title: Annotated[Optional[str], Field(description="Plot title")] = None,
    column_x: Annotated[int, Field(description="Column index for X data (0-based)")] = 0,
    column_y: Annotated[int, Field(description="Column index for Y data (0-based)")] = 1,
) -> dict:
    """Plot per-residue bar chart (RMSF, B-factors) as PNG."""
    try:
        result = md_agent.plot_bar(data_file, output_png, xlabel=xlabel, ylabel=ylabel, title=title, column_x=column_x, column_y=column_y)
        if isinstance(result, dict) and not result.get("success", True):
            return {"status": "error", "error": result.get("error", "plot failed"), "tool": "plot_bar"}
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


# ─── Protein structure prep (formerly CLI scripts) ────────────────────────────

@mcp.tool()
def cap_protein(
    input_pdb: Annotated[str, Field(description="Input PDB path (uncapped)")],
    output_pdb: Annotated[str, Field(description="Output PDB path (with ACE/NME caps, CYS→CYX disulfides)")],
) -> dict:
    """Add ACE/NME termini caps + auto-detect disulfide bonds (CYS→CYX).
    Strips incomplete terminal residues first. Wraps scripts/cap_protein.py logic.
    Returns disulfide pairs in tLEaP `bond` syntax for inclusion in tleap.in.
    """
    try:
        import cap_protein as _cp
        add_caps_script = str(_REPO_ROOT / "scripts" / "add_caps.py")

        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as tmp:
            tmp_pdb = tmp.name
        try:
            _cp.strip_incomplete_termini(input_pdb, tmp_pdb)
            r = subprocess.run(
                [PYTHON_BIN, add_caps_script, "-i", tmp_pdb, "-o", output_pdb],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                return {"status": "error", "stage": "add_caps", "stderr": r.stderr, "tool": "cap_protein"}
        finally:
            if os.path.exists(tmp_pdb):
                os.unlink(tmp_pdb)

        # CRIT-04 fix: add_caps.py (MDAnalysis mda.Merge) drops TER records.
        # Re-insert TER at every chain boundary so tLEaP builds correct topology.
        _ensure_ter_records(output_pdb)

        pairs = _cp.mark_disulfides(output_pdb)
        bond_cmds = [f"bond mol.{a}.SG mol.{b}.SG" for a, b in pairs]
        with open(output_pdb) as f:
            # M-01 fix: count both ATOM and HETATM (ligand-containing systems)
            n_atoms = sum(1 for l in f if l.startswith("ATOM") or l.startswith("HETATM"))
        return {
            "status": "ok",
            "output_pdb": output_pdb,
            "n_atoms": n_atoms,
            "disulfide_pairs": pairs,
            "tleap_bond_commands": bond_cmds,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "cap_protein"}


@mcp.tool()
def loop_model(
    pdb: Annotated[str, Field(description="Crystal PDB path with missing loops")],
    missing: Annotated[str, Field(description="Missing residue ranges e.g. 'A:86-91,A:120-125'")],
    uniprot: Annotated[str, Field(description="UniProt accession for AlphaFold lookup")],
    out: Annotated[str, Field(description="Output PDB path (filled-in)")],
    auto_low_confidence: Annotated[str, Field(description="Behavior when pLDDT < 70 for a region: 'accept' (graft anyway — default), 'reject' (require user_pdb_path), 'cap' (skip grafting — caller should cap at break), or 'prompt' (return error)")] = "accept",
    user_pdb_path: Annotated[Optional[str], Field(description="If auto_low_confidence='reject', path to user-provided PDB used as donor structure")] = None,
) -> dict:
    """Fill missing residue ranges in crystal PDB using AlphaFold (or ESMFold fallback).
    Non-interactive wrapper around scripts/loop_model.py — agent must pre-decide low-pLDDT behavior.
    Writes <out> + <out>.meta.json.
    """
    try:
        import loop_model as _lm

        missing_ranges = _lm.parse_missing_ranges(missing)
        meta = {
            "uniprot_id": uniprot,
            "missing_ranges": missing,
            "crystal_pdb": pdb,
            "source": None,
            "plddt": None,
            "action": "graft",
        }

        plddt_by_range = _lm.get_plddt_for_ranges(uniprot, missing_ranges)

        if plddt_by_range is not None:
            low_conf = {r: v for r, v in plddt_by_range.items() if v is not None and v < 70}

            if low_conf:
                if auto_low_confidence == "prompt":
                    return {
                        "status": "error",
                        "stage": "low_confidence_decision_required",
                        "low_confidence_regions": {f"{r[0]}:{r[1]}-{r[2]}": v for r, v in low_conf.items()},
                        "message": "pLDDT < 70 for some ranges. Re-call with auto_low_confidence='accept' (graft anyway), 'reject' + user_pdb_path=..., or 'cap' (skip — cap chains at break).",
                        "tool": "loop_model",
                    }
                if auto_low_confidence == "accept":
                    af_pdb = _lm.fetch_alphafold_pdb(uniprot)
                    if af_pdb is None:
                        return {"status": "error", "stage": "fetch_alphafold", "tool": "loop_model"}
                    _lm.extract_and_graft(pdb, af_pdb, missing_ranges, out)
                    meta["source"] = "AlphaFold (low-confidence, agent approved)"
                    # M-05 fix: use clean "A:86-91" format instead of tuple-stringified keys
                    meta["plddt"] = {f"{k[0]}:{k[1]}-{k[2]}": v for k, v in plddt_by_range.items()}
                elif auto_low_confidence == "reject":
                    # H-05 fix: use Path (already imported), not undefined _P
                    # H-06 fix: pass user_pdb_path (file path), not file contents
                    if not user_pdb_path or not Path(user_pdb_path).exists():
                        return {"status": "error", "stage": "user_pdb_missing", "tool": "loop_model",
                                "message": "auto_low_confidence='reject' requires existing user_pdb_path"}
                    _lm.extract_and_graft(pdb, user_pdb_path, missing_ranges, out)
                    meta["source"] = f"User-provided: {user_pdb_path}"
                elif auto_low_confidence == "cap":
                    meta["source"] = "Capped at break (agent decision)"
                    meta["action"] = "cap"
                    meta_path = out.replace(".pdb", ".meta.json")
                    with open(meta_path, "w") as f:
                        json.dump(meta, f, indent=2)
                    return {"status": "ok", "action": "cap", "meta_path": meta_path,
                            "message": "No grafting performed. Caller should run cap_protein on each segment at break points."}
                else:
                    return {"status": "error", "tool": "loop_model",
                            "message": f"Unknown auto_low_confidence='{auto_low_confidence}'. Use accept|reject|cap|prompt."}
            else:
                af_pdb = _lm.fetch_alphafold_pdb(uniprot)
                if af_pdb is None:
                    return {"status": "error", "stage": "fetch_alphafold", "tool": "loop_model"}
                _lm.extract_and_graft(pdb, af_pdb, missing_ranges, out)
                meta["source"] = "AlphaFold"
                meta["plddt"] = {str(k): v for k, v in plddt_by_range.items()}
        else:
            seq = _lm.get_sequence_from_pdb(pdb, chain=missing_ranges[0][0])
            if len(seq) <= 400:
                esm_pdb = _lm.call_esm_fold(seq)
                if esm_pdb is None:
                    return {"status": "error", "stage": "esmfold", "tool": "loop_model"}
                _lm.extract_and_graft(pdb, esm_pdb, missing_ranges, out)
                meta["source"] = "ESMFold"
            else:
                return {"status": "error", "tool": "loop_model",
                        "message": f"Protein > 400 AA ({len(seq)}) and not in AlphaFold DB. Provide complete-chain PDB."}

        meta_path = out.replace(".pdb", ".meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        return {"status": "ok", "out": out, "meta_path": meta_path, "source": meta["source"]}

    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "loop_model"}


# ─── Junction / Ligand Geometry Validation ───────────────────────────────────

@mcp.tool()
def validate_loop_junction(
    pdb_file: Annotated[str, Field(description="Path to PDB after loop_model or cap_protein")],
    min_bond: Annotated[float, Field(description="Minimum acceptable C-N distance in Å")] = 1.0,
    max_bond: Annotated[float, Field(description="Maximum acceptable C-N distance in Å")] = 1.7,
) -> dict:
    """Check all inter-residue C-N peptide bonds for sane geometry.

    Call this immediately after loop_model() completes a graft, before
    running tLEaP. A collapsed junction (< 1.0 Å) indicates the Kabsch
    alignment failed — the structure must NOT proceed to tLEaP.

    Args:
        pdb_file: path to PDB after loop_model or cap_protein.
        min_bond: minimum acceptable C-N distance in Å (default 1.0).
        max_bond: maximum acceptable C-N distance in Å (default 1.7).

    Returns:
        status=ok with tool field, or
        status=error with message describing the bad junction.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from loop_model import validate_junction_geometry
        validate_junction_geometry(pdb_file, min_bond=min_bond, max_bond=max_bond)
        return {"status": "ok", "tool": "validate_loop_junction", "pdb_file": pdb_file}
    except FileNotFoundError as e:
        return {"status": "error", "tool": "validate_loop_junction", "message": str(e)}
    except ValueError as e:
        return {"status": "error", "tool": "validate_loop_junction", "message": str(e)}
    except Exception as e:
        return {"status": "error", "tool": "validate_loop_junction", "message": str(e)}


# ─── Ligand Geometry Validation ─────────────────────────────────────────────

@mcp.tool()
def validate_ligand_geometry(
    mol2_file: Annotated[str, Field(description="Path to mol2 file output by antechamber")],
    max_h_distance: Annotated[float, Field(description="Maximum allowed H→heavy-atom distance in Å")] = 2.0,
) -> dict:
    """Check that every H atom in a mol2 file is ≤ max_h_distance Å from its heavy-atom neighbor.

    Call this after build_ligand_from_crystal() and before antechamber, to catch
    H-atom placement errors (e.g., 36 Å outliers caused by H-01 class bugs).
    Reads the mol2 file directly — no RDKit dependency needed.

    Args:
        mol2_file: path to mol2 file (antechamber output).
        max_h_distance: maximum allowed H→heavy distance in Å (default 2.0).

    Returns:
        status=ok with worst_h_distance, or
        status=error with the offending H atom name and distance.
    """
    import math
    try:
        if not Path(mol2_file).exists():
            return {"status": "error", "tool": "validate_ligand_geometry",
                    "message": f"File not found: {mol2_file}"}

        # Parse mol2: read @<TRIPOS>ATOM and @<TRIPOS>BOND sections
        atoms = {}   # atom_id → {name, element, x, y, z}
        bonds = []   # (atom_id_a, atom_id_b)

        in_atom = False
        in_bond = False
        with open(mol2_file) as f:
            for line in f:
                line = line.rstrip("\n")
                if line.startswith("@<TRIPOS>ATOM"):
                    in_atom = True
                    in_bond = False
                    continue
                if line.startswith("@<TRIPOS>BOND"):
                    in_atom = False
                    in_bond = True
                    continue
                if line.startswith("@<TRIPOS>"):
                    in_atom = False
                    in_bond = False
                    continue
                if in_atom and line.strip():
                    parts = line.split()
                    if len(parts) >= 6:
                        atom_id = int(parts[0])
                        atom_name = parts[1]
                        try:
                            x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
                        except ValueError:
                            continue
                        atom_type = parts[5]  # SYBYL type e.g. H, C.3, N.am
                        element = atom_type.split(".")[0].upper()
                        atoms[atom_id] = {"name": atom_name, "element": element, "x": x, "y": y, "z": z}
                if in_bond and line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            bonds.append((int(parts[1]), int(parts[2])))
                        except ValueError:
                            continue

        # Build adjacency: for each H, find bonded heavy neighbors
        worst_dist = 0.0
        worst_h = None
        errors = []
        for (a_id, b_id) in bonds:
            for h_id, heavy_id in ((a_id, b_id), (b_id, a_id)):
                if h_id not in atoms or heavy_id not in atoms:
                    continue
                h_atom = atoms[h_id]
                heavy_atom = atoms[heavy_id]
                if h_atom["element"] != "H":
                    continue
                if heavy_atom["element"] == "H":
                    continue
                dx = h_atom["x"] - heavy_atom["x"]
                dy = h_atom["y"] - heavy_atom["y"]
                dz = h_atom["z"] - heavy_atom["z"]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist > worst_dist:
                    worst_dist = dist
                    worst_h = h_atom["name"]
                if dist > max_h_distance:
                    errors.append({
                        "h_atom": h_atom["name"],
                        "heavy_atom": heavy_atom["name"],
                        "distance_angstrom": round(dist, 3),
                    })

        if errors:
            return {
                "status": "error",
                "tool": "validate_ligand_geometry",
                "message": f"{len(errors)} H atom(s) too far from heavy neighbor (>{max_h_distance} Å)",
                "worst_h_distance": round(worst_dist, 3),
                "worst_h_atom": worst_h,
                "violations": errors,
            }
        return {
            "status": "ok",
            "tool": "validate_ligand_geometry",
            "mol2_file": mol2_file,
            "worst_h_distance": round(worst_dist, 3),
            "n_h_atoms_checked": sum(1 for v in atoms.values() if v["element"] == "H"),
        }
    except Exception as e:
        return {"status": "error", "tool": "validate_ligand_geometry", "message": str(e)}


# ─── Protonation (propka3 + override application) ────────────────────────────

def _his_hbond_tautomer(pdb_path: str, his_list: list) -> dict:
    """
    For each ambiguous HIS (pKa 6–8), inspect PDB H-bond network to assign HID or HIE.

    Logic:
      - HID: proton on ND1 → NE2 is bare acceptor. Assign HID when a H-bond donor
            (N, O-H, N-H) is within 3.5 Å of NE2 (NE2 accepts → must be bare).
      - HIE: proton on NE2 → ND1 is bare acceptor. Assign HIE when a H-bond donor
            is within 3.5 Å of ND1 (ND1 accepts → must be bare).
      - Metal near either N → HID (kinase/metalloprotein convention: ND1 coordinates).
      - Conflicting or no signal → HID (safe default).

    Returns dict: {(chain, resnum): {"tautomer": "HID"|"HIE", "reason": str}}
    """
    import math

    CUTOFF = 3.5  # heavy-atom H-bond distance Å
    # Atom names that can donate an H-bond (have attached H in typical protonation state)
    DONORS = {"N", "NZ", "NH1", "NH2", "NE", "NE1", "ND2", "OG", "OG1", "OH", "OXT", "O"}
    # PRO backbone N is not a donor (no H) — excluded by resname check below
    METALS = {"FE", "ZN", "MG", "MN", "CA", "CU", "CO", "NI", "MO"}

    # Parse all heavy atoms
    all_atoms = []
    with open(pdb_path) as fh:
        for line in fh:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            try:
                aname   = line[12:16].strip()
                resname = line[17:20].strip()
                chain   = line[21]
                resnum  = int(line[22:26])
                x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
                all_atoms.append((chain, resnum, resname, aname, x, y, z))
            except (ValueError, IndexError):
                continue

    results = {}

    for his in his_list:
        ch, rn = his["chain"], his["resnum"]

        # Locate ND1 and NE2 of this HIS
        nd1 = ne2 = None
        for (ac, ar, ares, aname, ax, ay, az) in all_atoms:
            if ac == ch and ar == rn and ares in ("HIS", "HID", "HIE", "HIP"):
                if aname == "ND1":
                    nd1 = (ax, ay, az)
                elif aname == "NE2":
                    ne2 = (ax, ay, az)

        if nd1 is None or ne2 is None:
            results[(ch, rn)] = {"tautomer": "HID", "reason": "ND1/NE2 not found in PDB — default HID"}
            continue

        def d(p1, p2):
            return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))

        metal_near  = False
        donors_nd1  = []   # donors within CUTOFF of ND1 → ND1 accepts → HIE
        donors_ne2  = []   # donors within CUTOFF of NE2 → NE2 accepts → HID

        for (ac, ar, ares, aname, ax, ay, az) in all_atoms:
            if ac == ch and ar == rn:
                continue  # skip self
            pos = (ax, ay, az)

            # Metal coordination → HID
            el = aname.rstrip("0123456789").upper()
            if el in METALS or ares.upper() in METALS:
                if d(nd1, pos) < 3.0 or d(ne2, pos) < 3.0:
                    metal_near = True
                continue

            # PRO backbone N is not a donor
            is_donor = aname in DONORS and not (aname == "N" and ares == "PRO")

            if is_donor:
                if d(nd1, pos) < CUTOFF:
                    donors_nd1.append(f"{ares}{ar}:{aname}")
                if d(ne2, pos) < CUTOFF:
                    donors_ne2.append(f"{ares}{ar}:{aname}")

        if metal_near:
            taut = "HID"
            reason = "metal coordination near HIS N atoms → HID"
        elif len(donors_nd1) > 0 and len(donors_ne2) == 0:
            taut = "HIE"
            reason = f"H-bond donor(s) near ND1 ({', '.join(donors_nd1)}) → ND1 accepts → HIE"
        elif len(donors_ne2) > 0 and len(donors_nd1) == 0:
            taut = "HID"
            reason = f"H-bond donor(s) near NE2 ({', '.join(donors_ne2)}) → NE2 accepts → HID"
        elif len(donors_nd1) > len(donors_ne2):
            taut = "HIE"
            reason = (f"more donors near ND1 ({len(donors_nd1)}) than NE2 ({len(donors_ne2)}) → HIE")
        elif len(donors_ne2) > len(donors_nd1):
            taut = "HID"
            reason = (f"more donors near NE2 ({len(donors_ne2)}) than ND1 ({len(donors_nd1)}) → HID")
        else:
            taut = "HID"
            reason = "no clear H-bond signal (no donors within 3.5 Å of either N) → default HID"

        results[(ch, rn)] = {"tautomer": taut, "reason": reason}

    return results

@mcp.tool()
def run_propka3(
    pdb_path: Annotated[str, Field(description="Path to protein PDB (no HETATM ligand, no waters; stripped via mcp__amber__strip_hetatm or grep ^ATOM first)")],
    pH: Annotated[float, Field(description="Target pH for protonation suggestions. Choose based on protein cellular compartment: 7.4 (extracellular/blood, default), 7.0-7.2 (cytoplasm/nucleus), 5.0-6.0 (endosome/lysosome), 7.8 (mitochondrial matrix)")] = 7.4,
) -> dict:
    """Run propka3 on protein PDB, parse pKa SUMMARY section, suggest non-standard Amber protonation states.

    Decision rules (vs pH):
      - HIS pKa < 6.0 → HID (strongly deprotonated — pKa far below pH, ~95% neutral)
      - HIS 6.0 ≤ pKa ≤ 8.0 → ambiguous (note added — inspect H-bond network → HID/HIE)
      - HIS pKa > 8.0 → HIP (strongly protonated — pKa far above pH, ~95% +1 charged)
      - ASP pKa > pH → ASH (buried, protonated)
      - GLU pKa > pH → GLH (buried, protonated)
      - LYS pKa < pH → LYN (deprotonated)
      - CYS pKa < pH → CYM (note — verify NOT a disulfide; cap_protein assigns CYX)

    Returns full pKa table + suggested_overrides list ready for apply_protonation_overrides.
    Does NOT modify the PDB.
    """
    try:
        if not os.path.exists(pdb_path):
            return {"status": "error", "error": f"PDB not found: {pdb_path}", "tool": "run_propka3"}
        if not os.path.exists(PROPKA_BIN):
            return {"status": "error", "error": f"propka3 binary not found: {PROPKA_BIN}", "tool": "run_propka3"}
        pdb_dir = os.path.dirname(os.path.abspath(pdb_path)) or "."
        pdb_base = os.path.basename(pdb_path)
        pka_file = os.path.join(pdb_dir, pdb_base.rsplit(".", 1)[0] + ".pka")

        # propka3 cache: reuse .pka if PDB unchanged (same mtime) and pH matches.
        # Cache tag stored in first line comment of .pka: "# pH=X mtime=Y"
        _cache_hit = False
        try:
            pdb_mtime = os.path.getmtime(pdb_path)
            if os.path.exists(pka_file):
                with open(pka_file) as _f:
                    _first = _f.readline()
                if f"pH={pH}" in _first and f"mtime={pdb_mtime:.2f}" in _first:
                    _cache_hit = True
        except Exception:
            pass

        if not _cache_hit:
            r = subprocess.run(
                [PROPKA_BIN, "-o", str(pH), pdb_base],
                capture_output=True, text=True, cwd=pdb_dir,
            )
            if r.returncode != 0:
                return {"status": "error", "stage": "propka3_run", "stderr": r.stderr[-2000:],
                        "stdout": r.stdout[-1000:], "tool": "run_propka3"}
            # Prepend cache tag to .pka for future hits
            if os.path.exists(pka_file):
                try:
                    _pka_content = open(pka_file).read()
                    with open(pka_file, "w") as _f:
                        _f.write(f"# pH={pH} mtime={pdb_mtime:.2f}\n" + _pka_content)
                except Exception:
                    pass
        if not os.path.exists(pka_file):
            return {"status": "error", "error": f"Output .pka not found: {pka_file}", "tool": "run_propka3"}

        with open(pka_file) as f:
            text = f.read()

        summary_idx = text.find("SUMMARY OF THIS PREDICTION")
        if summary_idx < 0:
            return {"status": "error", "error": "SUMMARY section not found in .pka", "tool": "run_propka3"}

        line_re = re.compile(r"^\s+([A-Z][A-Z0-9+-]{1,3})\s+(\d+)\s+([A-Z])\s+(-?\d+\.\d+)\*?\s+(-?\d+\.\d+)")
        residues = []
        for ln in text[summary_idx:].splitlines():
            m = line_re.match(ln)
            if m:
                resname = m.group(1)
                if resname in ("N+", "C-"):
                    continue
                residues.append({
                    "resname": resname, "resnum": int(m.group(2)), "chain": m.group(3),
                    "pKa": float(m.group(4)), "model_pKa": float(m.group(5)),
                })

        suggested = []
        notes = []
        # Collect ambiguous HIS for H-bond analysis (done once, after loop)
        ambiguous_his = []
        for rec in residues:
            rn, num, ch, pka = rec["resname"], rec["resnum"], rec["chain"], rec["pKa"]
            if rn == "HIS":
                if pka < 6.0:
                    suggested.append({**rec, "new_resname": "HID",
                                       "reason": f"pKa {pka:.2f} < 6.0 → strongly deprotonated at pH {pH}"})
                elif pka > 8.0:
                    suggested.append({**rec, "new_resname": "HIP",
                                       "reason": f"pKa {pka:.2f} > 8.0 → strongly protonated at pH {pH}"})
                else:
                    ambiguous_his.append(rec)
            elif rn == "ASP" and pka > pH:
                suggested.append({**rec, "new_resname": "ASH",
                                   "reason": f"pKa {pka:.2f} > pH {pH} → protonated (buried)"})
            elif rn == "GLU" and pka > pH:
                suggested.append({**rec, "new_resname": "GLH",
                                   "reason": f"pKa {pka:.2f} > pH {pH} → protonated (buried)"})
            elif rn == "LYS" and pka < pH:
                suggested.append({**rec, "new_resname": "LYN",
                                   "reason": f"pKa {pka:.2f} < pH {pH} → deprotonated"})
            elif rn == "CYS" and pka < pH:
                notes.append({**rec,
                               "note": f"CYS pKa {pka:.2f} < pH {pH} suggests CYM — VERIFY no disulfide "
                                       "(cap_protein assigns CYX for disulfides already)"})

        # H-bond network analysis for ambiguous HIS (pKa 6–8)
        if ambiguous_his:
            try:
                hbond_results = _his_hbond_tautomer(pdb_path, ambiguous_his)
                for rec in ambiguous_his:
                    key = (rec["chain"], rec["resnum"])
                    hr = hbond_results.get(key)
                    if hr:
                        suggested.append({
                            **rec,
                            "new_resname": hr["tautomer"],
                            "reason": f"pKa {rec['pKa']:.2f} in 6–8 range; H-bond analysis: {hr['reason']}",
                        })
                    else:
                        notes.append({**rec,
                                       "note": f"HIS pKa {rec['pKa']:.2f} in 6–8 range — H-bond analysis failed; default HID"})
            except Exception as hb_err:
                # H-bond analysis failed — fall back to notes (non-fatal)
                for rec in ambiguous_his:
                    notes.append({**rec,
                                   "note": f"HIS pKa {rec['pKa']:.2f} in 6–8 range — H-bond analysis error ({hb_err}); default HID"})

        return {
            "status": "ok",
            "pka_file": pka_file,
            "pH": pH,
            "n_residues_titrated": len(residues),
            "residues": residues,
            "suggested_overrides": suggested,
            "notes": notes,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "run_propka3"}


@mcp.tool()
def apply_protonation_overrides(
    pdb_in: Annotated[str, Field(description="Input PDB path")],
    pdb_out: Annotated[str, Field(description="Output PDB path with renamed residues")],
    overrides: Annotated[list, Field(description="List of dicts: {resname, resnum, chain, new_resname}. Only ATOM/HETATM records matching all three keys are renamed.")],
) -> dict:
    """Rename specific residues in PDB to non-standard Amber protonation states (HIP/HID/HIE/ASH/GLH/LYN/CYM).

    Each override: {"resname": "HIS", "resnum": 57, "chain": "A", "new_resname": "HIP"}
    Only rewrites residue-name columns (18-20); coordinates and all other fields preserved exactly.
    Returns count applied vs requested + list of overrides not matched in PDB.
    """
    try:
        if not overrides:
            return {"status": "error", "error": "No overrides provided", "tool": "apply_protonation_overrides"}
        lookup = {}
        for ov in overrides:
            key = (str(ov["chain"]), int(ov["resnum"]), str(ov["resname"]).strip())
            new_resname = str(ov["new_resname"]).strip()
            # M-02 fix: validate new_resname is a valid 1-3 letter Amber residue name
            if not (1 <= len(new_resname) <= 3 and new_resname.isalnum()):
                return {"status": "error", "error": f"Invalid new_resname '{new_resname}': must be 1-3 alphanumeric chars", "tool": "apply_protonation_overrides"}
            lookup[key] = new_resname

        applied = set()
        with open(pdb_in) as f_in, open(pdb_out, "w") as f_out:
            for line in f_in:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    resname = line[17:20].strip()
                    chain = line[21]
                    try:
                        resnum = int(line[22:26].strip())
                    except ValueError:
                        f_out.write(line)
                        continue
                    key = (chain, resnum, resname)
                    if key in lookup:
                        new = lookup[key].ljust(3)[:3]
                        line = line[:17] + new + line[20:]
                        applied.add(key)
                f_out.write(line)

        missed = [{"resname": k[2], "resnum": k[1], "chain": k[0]} for k in lookup if k not in applied]
        return {
            "status": "ok",
            "output_pdb": pdb_out,
            "overrides_applied": len(applied),
            "overrides_requested": len(lookup),
            "missing_in_pdb": missed,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "apply_protonation_overrides"}


# ─── Ligand build (CCD coord-transplant pipeline) ─────────────────────────────

# Priority-ordered SMARTS charge correction rules for pH 7.4.
# Apply most-specific-first; atom-claiming prevents overlap (e.g. guanidine before amidine).
# +0 constraints on ionizable groups prevent double-counting with CCD permanent charges.
# final_charge = rdkit_charge (CCD permanent) + smarts_delta (neutral → pH-7.4 correction).
_LIGAND_CHARGE_RULES = [
    # P1: Guanidine before amidine (guanidine matches amidine SMARTS too).
    # EW exclusions: cyanoguanidine (NC#N), nitroguanidine (N-NO2), sulfonylguanidine (N-SO2)
    # are NOT basic at pH 7.4 — pKa near 0 due to electron withdrawal.
    ("guanidine",
     "[NX3;+0;!$(NC#N);!$(N[N+](=O)[O-]);!$(NS(=O)(=O))]"
     "[CX3]"
     "(=[NX2;+0;!$(NC#N);!$(N[N+](=O)[O-]);!$(NS(=O)(=O))])"
     "[NX3;+0;!$(NC#N);!$(N[N+](=O)[O-]);!$(NS(=O)(=O))]",
     +1, "auto"),
    # P2: Phosphates before phosphonic acid
    ("phosphate_free",       "[PX4](=O)([OX2H1;+0])([OX2H1;+0])[OX2H1;+0]",   -2, "auto"),
    ("phosphate_monoester",  "[PX4](=O)([OX2H1;+0])([OX2H1;+0])[OX2H0;+0]",   -2, "auto"),
    # CRIT-06 fix: phosphoanhydride internal P (α/β in ATP, ADP, GTP etc.).
    # Terminal P (γ) has 2 OH → matched by phosphate_monoester above (-2).
    # Internal P has 1 OH + 2 bridging O (anhydride or ester, no H, no charge) → -1 each.
    # Verified: β-P in ATP [PX4](=O)(OH)(O-bridge-α)(O-bridge-γ) → matches; RNA phosphodiester
    # has no OH → does NOT match. Gives ATP total = -2 (γ) + -1 (β) + -1 (α) = -4. ✓
    ("phosphoanhydride_internal",
     "[PX4](=O)([OX2H1;+0])([OX2H0;+0])[OX2H0;+0]",                           -1, "auto"),
    ("phosphonic_acid",      "[PX4](=O)([OX2H1;+0])[#6]",                        0, "flag"),
    # P4: Tetrazole (acidic N-H, before generic N-H patterns)
    ("tetrazole",            "c1nnn[nH]1",                                       -1, "auto"),
    # P5: Amidine (after guanidine claimed atoms). Same EW exclusions.
    # Extra guard on central C: !$([CX3]([NX3])(=[NX2])[NX3]) blocks guanidine-topology C
    # (two NX3 + one NX2) even when the guanidine rule was excluded by an EW group —
    # prevents amidine from matching the NH2-C=NH fragment of sulfonamidoguanidine (famotidine).
    # Guards on [NX3]: !$(N1CCNCC1) prevents piperazine ring N from being the amino side
    #   (clozapine/quetiapine class: piperazine N is the =N partner, diazepine ring-NH
    #   is the NX3 partner — Kekulé assignment makes both non-aromatic, so [nH] test fails).
    # !$([nH]) keeps aromatic-NH from matching. !$([n]) on [NX2] keeps aromatic ring N off.
    ("amidine",
     "[NX3;+0;!$(N1CCNCC1);!$([nH]);!$(NC#N);!$(N[N+](=O)[O-]);!$(NS(=O)(=O))]"
     "[CX3;!$([CX3]([NX3])(=[NX2])[NX3])]"
     "=[NX2;+0;!$([n]);!$(NC#N);!$(N[N+](=O)[O-]);!$(NS(=O)(=O))]",
     +1, "auto"),
    # P6: Acid groups
    ("carboxylic_acid",      "[CX3](=O)[OX2H1;+0]",                             -1, "auto"),
    ("sulfonic_acid",        "[SX4](=O)(=O)[OX2H1;+0]",                         -1, "auto"),
    ("sulfinic_acid",        "[SX3](=O)[OX2H1;+0]",                             -1, "auto"),
    # P7a: Dialkylated piperazine ring — both Ns fully alkylated (H0), all sp3 neighbors.
    # Only first piperazine pKa (~9) is > 7.4; second pKa (~5) is not. Claim both Ns → +1.
    # Must come before aliphatic_tert_amine to prevent double-counting.
    ("piperazine_dialkyl",   "[NX3;H0;+0]1[CX4][CX4][NX3;H0;+0][CX4][CX4]1",  +1, "auto"),
    # P7b: Aliphatic N only — CX4 excludes aromatic/carbonyl neighbors (aniline pKa ~4 = neutral)
    ("aliphatic_prim_amine", "[NX3;H2;+0][CX4]",                                +1, "auto"),
    ("aliphatic_sec_amine",  "[NX3;H1;+0]([CX4])[CX4]",                         +1, "auto"),
    ("aliphatic_tert_amine", "[NX3;H0;+0]([CX4])([CX4])[CX4]",                 +1, "auto"),
    # P8: Neutral groups — explicit 0, no correction, atom-claimed to stop lower rules firing
    ("imidazole",            "c1cnc[nH]1",                                        0, "neutral"),
    ("pyridine_N",           "[nX2]",                                              0, "neutral"),
    ("aniline",              "[NX3;H2]c",                                          0, "neutral"),
    ("amide_N",              "[NX3][CX3]=[OX1]",                                  0, "neutral"),
    ("alcohol",              "[CX4][OX2H1]",                                       0, "neutral"),
    ("phenol",               "c[OX2H1]",                                           0, "neutral"),
    # P9: Ambiguous — hard stop, agent must ask user
    ("thiol",                "[#6][SX2H1]",                                        0, "flag"),
]

# Maps each SMARTS rule to (match_tuple_index, formal_charge) pairs.
# Index refers to atom position in SMARTS traversal order (same order RDKit returns in match tuple).
# Called BEFORE AddHs; formal charges drive correct implicit-H count via UpdatePropertyCache.
_RULE_CHARGE_ATOM = {
    "guanidine":            [(2, +1)],   # match[2]=NX2 imino N; N+ dbl-bond → valence4-2=2H
    "phosphate_free":       [(2, -1), (3, -1)],  # two of three OX2H1 → O- valence1-1=0H; net -2
    "phosphate_monoester":  [(2, -1), (3, -1)],  # two OX2H1 → O-; net -2
    "amidine":              [(2, +1)],   # match[2]=NX2 imino N → N+H2
    "carboxylic_acid":      [(2, -1)],   # match[2]=OX2H1 → O- (0H)
    "sulfonic_acid":        [(3, -1)],   # match[3]=OX2H1 → O-
    "sulfinic_acid":        [(2, -1)],   # match[2]=OX2H1 → O-
    "tetrazole":            [(4, -1)],   # match[4]=[nH] aromatic N → n- (H cleared explicitly)
    "piperazine_dialkyl":   [(0, +1)],   # match[0]=first N (H0) → N+H1
    "aliphatic_prim_amine": [(0, +1)],   # match[0]=N → N+H3
    "aliphatic_sec_amine":  [(0, +1)],   # match[0]=N → N+H2
    "aliphatic_tert_amine": [(0, +1)],   # match[0]=N → N+H1
}


def _apply_ph74_charges(mol):
    """Set formal charges on heavy-atom mol for pH 7.4 protonation state.

    Call BEFORE AddHs. Sets formal charges so RDKit computes correct implicit-H
    count after mol.UpdatePropertyCache(strict=False).

    Returns (mol_with_charges, net_delta, matched_groups, flags).
    """
    from rdkit import Chem
    rw = Chem.RWMol(mol)
    claimed, delta, matched, flags = set(), 0, [], []

    for name, smarts, rule_delta, action in _LIGAND_CHARGE_RULES:
        patt = Chem.MolFromSmarts(smarts)
        if patt is None:
            continue
        for match in mol.GetSubstructMatches(patt):
            if set(match) & claimed:
                continue
            claimed |= set(match)

            if action == "auto":
                delta += rule_delta
                matched.append(f"{name}({rule_delta:+d})")
                charge_specs = _RULE_CHARGE_ATOM.get(name)
                if charge_specs is not None:
                    for midx, fc in charge_specs:
                        if midx < len(match):
                            atom = rw.GetAtomWithIdx(match[midx])
                            atom.SetFormalCharge(fc)
                            atom.SetNoImplicit(False)
                            if fc < 0 and atom.GetIsAromatic():
                                # Aromatic NH (tetrazole): explicit H must be cleared
                                atom.SetNumExplicitHs(0)
                                atom.SetNoImplicit(True)
            elif action == "flag":
                flags.append(name)

    mol_out = rw.GetMol()
    mol_out.UpdatePropertyCache(strict=False)
    return mol_out, delta, matched, flags


def _correct_ligand_charge(mol):
    """Return (corrected_charge, matched_groups, flags, charge_source) for mol at pH 7.4.

    corrected_charge = rdkit_charge (CCD permanent) + smarts_delta (neutral group ionization).
    mol must have explicit H (Chem.AddHs already called).
    """
    from rdkit import Chem
    rdkit_charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())

    claimed, smarts_delta, matched, flags = set(), 0, [], []
    for name, smarts, delta, action in _LIGAND_CHARGE_RULES:
        patt = Chem.MolFromSmarts(smarts)
        if patt is None:
            continue
        for match in mol.GetSubstructMatches(patt):
            if set(match) & claimed:
                continue
            claimed |= set(match)
            if action == "auto":
                smarts_delta += delta
                matched.append(f"{name}({delta:+d})")
            elif action == "flag":
                flags.append(name)

    corrected = rdkit_charge + smarts_delta
    if flags:
        charge_source = "flags_present"
    elif matched:
        charge_source = "smarts_corrected"
    else:
        charge_source = "ccd"
    return corrected, matched, flags, charge_source


@mcp.tool()
def build_ligand_from_crystal(
    resname: Annotated[str, Field(description="3-letter HETATM residue name (e.g. 'BEN')")],
    pdb_path: Annotated[str, Field(description="Path to crystal PDB containing HETATM ligand")],
    out_sdf: Annotated[str, Field(description="Output SDF path — protonated ligand ready for antechamber")],
) -> dict:
    """Build antechamber-ready ligand SDF from crystal HETATM, preserving crystal geometry exactly.

    Pipeline:
      1. Extract HETATM block (single chain) → connectivity + crystal 3D coords (sanitize=False)
      2. Bond orders: try CCD ideal SDF via AssignBondOrdersFromTemplate (primary).
         Fallback: RDKit valence perception (works for simple ligands; fails for aromatics
         without bond info — returns clear error for exotic cases).
      3. SMARTS pH-7.4 charge rules → set formal charges on heavy atoms
         (SetNoImplicit + UpdatePropertyCache so AddHs uses correct valence)
      4. AddHs(addCoords=True) → H placed geometrically around crystal coords,
         count matches pH-7.4 protonation state (NH3+ not NH2, COO- not COOH)
      5. Write SDF; return net charge for antechamber -nc flag

    Crystal heavy-atom coordinates are never modified. Only H atoms are added.
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        # Step 1: extract HETATM (single chain), parse without sanitize to preserve coords
        seen_chain, het_lines = None, []
        with open(pdb_path) as f:
            for line in f:
                if line.startswith("HETATM") and line[17:20].strip() == resname:
                    chain = line[21]
                    if seen_chain is None:
                        seen_chain = chain
                    if chain == seen_chain:
                        het_lines.append(line)

        if not het_lines:
            return {"status": "error", "stage": "extract_crystal",
                    "error": f"No HETATM for {resname} in {pdb_path}",
                    "tool": "build_ligand_from_crystal"}

        crystal_mol = Chem.MolFromPDBBlock(
            "".join(het_lines) + "END\n", removeHs=True, sanitize=False,
        )
        if crystal_mol is None:
            return {"status": "error", "stage": "crystal_parse",
                    "error": "RDKit failed to parse HETATM block",
                    "tool": "build_ligand_from_crystal"}
        if crystal_mol.GetNumConformers() == 0:
            return {"status": "error", "stage": "crystal_conformer",
                    "error": "Crystal mol has no 3D conformer — PDB block malformed",
                    "tool": "build_ligand_from_crystal"}

        heavy_count = crystal_mol.GetNumAtoms()
        bond_order_source = "rdkit"

        # Step 2: bond orders — CCD primary, RDKit fallback
        try:
            url = f"https://files.rcsb.org/ligands/download/{resname}_ideal.sdf"
            data = urllib.request.urlopen(url, timeout=15).read().decode()
            ccd_mol = Chem.MolFromMolBlock(data, removeHs=False, sanitize=True)
            if ccd_mol is not None:
                ccd_heavy = Chem.RemoveAllHs(ccd_mol)
                if ccd_heavy.GetNumAtoms() == heavy_count:
                    crystal_mol = AllChem.AssignBondOrdersFromTemplate(ccd_heavy, crystal_mol)
                    bond_order_source = "ccd"
                else:
                    bond_order_source = "rdkit_atom_mismatch"
        except Exception:
            bond_order_source = "rdkit_fetch_fail"

        # Sanitize (post-template or RDKit's own perception)
        try:
            Chem.SanitizeMol(crystal_mol)
        except Exception as san_err:
            return {"status": "error", "stage": "sanitize",
                    "error": (f"Bond order perception failed: {san_err}. "
                              f"bond_order_source={bond_order_source}. "
                              "For exotic valence (metal complex, unusual oxidation state) "
                              "provide pre-protonated SDF via Branch A instead."),
                    "tool": "build_ligand_from_crystal"}

        # Step 3: SMARTS pH-7.4 → formal charges on heavy atoms
        mol_charged, delta, titratable_groups, charge_flags = _apply_ph74_charges(crystal_mol)
        ccd_charge = sum(a.GetFormalCharge() for a in crystal_mol.GetAtoms())
        net_charge = ccd_charge + delta
        charge_source = ("flags_present" if charge_flags
                         else "smarts_corrected" if titratable_groups
                         else "crystal_formal")

        # Step 4: AddHs — crystal heavy coords intact; H placed from valence geometry
        mol_H = Chem.AddHs(mol_charged, addCoords=True)
        h_added = sum(1 for a in mol_H.GetAtoms() if a.GetAtomicNum() == 1)

        # Step 5: write SDF
        out_dir = os.path.dirname(out_sdf) or "."
        os.makedirs(out_dir, exist_ok=True)
        with Chem.SDWriter(out_sdf) as w:
            w.write(mol_H)

        return {
            "status": "ok",
            "out_sdf": out_sdf,
            "charge": net_charge,
            "antechamber_nc_flag": net_charge,
            "charge_source": charge_source,
            "titratable_groups": titratable_groups,
            "charge_flags": charge_flags,
            "bond_order_source": bond_order_source,
            "h_added": h_added,
            "heavy_atoms": heavy_count,
            "ligand_chain": seen_chain,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "tool": "build_ligand_from_crystal"}


if __name__ == "__main__":
    mcp.run()

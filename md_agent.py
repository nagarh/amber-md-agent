#!/usr/bin/env python3
"""
AmberMD Agent — Toolkit for AI-driven Molecular Dynamics.

This is NOT a hardcoded pipeline. It is a TOOLKIT that Claude Code
(the AI agent) uses dynamically. When a user asks for any workflow —
standard MD, umbrella sampling, TI, REMD, steered MD, MM-PBSA —
the agent:

  1. Queries the Amber manual via RAG to understand the protocol
  2. Plans the steps needed
  3. Uses these tool functions to execute each step
  4. Reads output, diagnoses errors, adapts

The AI agent is the brain. This file is the hands.

Usage (direct CLI for quick tasks):
    python md_agent.py fetch 1UBQ
    python md_agent.py inspect system.pdb
    python md_agent.py clean raw.pdb
    python md_agent.py rag-ingest Amber24.pdf
    python md_agent.py rag-query "how to set up umbrella sampling"
    python md_agent.py check-env
    python md_agent.py run-amber <engine> -i input.mdin -o out.mdout -p top.prmtop -c coords.rst7
    python md_agent.py cpptraj <script.in>
    python md_agent.py write-mdin output.mdin --params '{"imin":1,"maxcyc":5000}'
    python md_agent.py write-tleap output.in --commands "source leaprc.protein.ff19SB; ..."
    python md_agent.py energy prod.mdout
    python md_agent.py convergence rmsd.dat
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import shutil
import time
import logging
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
REFERENCES_DIR = BASE_DIR / "references"

# RAG index cache — loaded once per index path, reused across all queries in same session
_rag_index_cache: dict = {}

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("amber_md")

STANDARD_AA = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY",
    "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER",
    "THR", "TRP", "TYR", "VAL", "HID", "HIE", "HIP", "CYX",
    "ACE", "NME",
}


# ─── Cluster Configuration ────────────────────────────────────────────────────

def load_slurm_config():
    """Load cluster settings from scripts/slurm_template.sh.

    Reads raw #SBATCH lines and environment setup lines from the template.
    These are injected verbatim into generated job scripts so users can paste
    exactly what their cluster documentation specifies.

    Returns a dict with:
        sbatch_lines: list of "#SBATCH ..." strings
        env_lines:    list of "module load ..." / "source ..." strings
        WORK_BASE:    optional base path for studies
    """
    defaults = {
        "sbatch_lines": [
            "#SBATCH --partition=defq",
            "#SBATCH --nodes=1",
            "#SBATCH --ntasks-per-node=1",
            "#SBATCH --cpus-per-task=1",
            "#SBATCH --gres=gpu:1",
            "#SBATCH --time=168:00:00",
        ],
        "env_lines": ["module load amber/24"],
        "WORK_BASE": "",
    }
    template = BASE_DIR / "scripts" / "slurm_template.sh"
    if not template.exists():
        return defaults

    sbatch_lines, env_lines, work_base = [], [], ""
    for raw in template.read_text().splitlines():
        line = raw.strip()
        if line.startswith("#SBATCH"):
            sbatch_lines.append(line)
        elif line.startswith("module ") or line.startswith("source "):
            env_lines.append(line)
        elif line.startswith("WORK_BASE="):
            work_base = line.split("=", 1)[1].strip().strip('"').strip("'")

    return {
        "sbatch_lines": sbatch_lines if sbatch_lines else defaults["sbatch_lines"],
        "env_lines":    env_lines    if env_lines    else defaults["env_lines"],
        "WORK_BASE":    work_base,
    }


def _filter_sbatch(sbatch_lines, exclude_directives):
    """Remove lines whose directive name appears in exclude_directives.

    e.g. exclude_directives={"partition", "time"} removes
    "#SBATCH --partition=..." and "#SBATCH --time=..." from the list.
    """
    result = []
    for line in sbatch_lines:
        parts = line.split(None, 1)          # ["#SBATCH", "--partition=defq"]
        if len(parts) == 2:
            directive = parts[1].lstrip("-").split("=")[0]   # "partition"
            if directive in exclude_directives:
                continue
        result.append(line)
    return result


SLURM_CONFIG = load_slurm_config()


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE UTILITIES — low-level helpers the agent calls
# ═══════════════════════════════════════════════════════════════════════════════

def run_cmd(cmd, cwd=None, check=True, capture=True, timeout=None):
    """Run a shell command. Returns CompletedProcess."""
    logger.info(f"$ {cmd}")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd, check=False,
        capture_output=capture, text=True, timeout=timeout
    )
    if result.returncode != 0:
        logger.error(f"Exit code {result.returncode}")
        if capture and result.stderr:
            logger.error(f"STDERR:\n{result.stderr[-3000:]}")
        if check:
            raise RuntimeError(f"Command failed: {cmd}\n{result.stderr[-1000:]}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: Environment Check
# ═══════════════════════════════════════════════════════════════════════════════

def check_environment():
    """Report what Amber tools and resources are available.
    The agent uses this to decide what's possible."""
    report = {"tools": {}, "gpu": None, "md_engine": "sander", "python_libs": {}}

    amber_tools = [
        "tleap", "sander", "pmemd", "pmemd.cuda", "pmemd.MPI",
        "cpptraj", "pytraj", "antechamber", "parmchk2", "pdb4amber",
        "parmed", "MMPBSA.py", "FEW.py",
        "sander.LES", "pmemd.cuda.MPI",
    ]
    for tool in amber_tools:
        path = shutil.which(tool)
        report["tools"][tool] = path if path else False

    for engine in ["pmemd.cuda", "pmemd.cuda.MPI", "pmemd", "pmemd.MPI", "sander"]:
        if report["tools"].get(engine):
            report["md_engine"] = engine
            break

    try:
        r = run_cmd("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader",
                     check=False, capture=True)
        if r.returncode == 0 and r.stdout.strip():
            report["gpu"] = r.stdout.strip()
    except Exception:
        pass

    for lib in ["numpy", "matplotlib", "scipy", "mdtraj", "pytraj",
                "parmed", "PyPDF2", "pdfminer"]:
        try:
            __import__(lib)
            report["python_libs"][lib] = True
        except ImportError:
            report["python_libs"][lib] = False

    index_path = REFERENCES_DIR / "amber_index.json"
    report["rag_index_available"] = index_path.exists()
    if index_path.exists():
        try:
            idx = json.loads(index_path.read_text())
            n_pages = idx.get("n_pages") or idx.get("n_docs") or len(idx.get("pages", []))
            report["rag_pages"] = n_pages
            report["rag_chunks"] = n_pages
        except Exception as exc:
            report["rag_pages"] = None
            report["rag_chunks"] = None
            report["rag_index_error"] = str(exc)

    try:
        r = run_cmd("sacct --help", check=False, capture=True)
        report["sacct_available"] = (r.returncode == 0 and "accounting storage is disabled" not in r.stderr.lower())
    except Exception:
        report["sacct_available"] = False

    return report


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: PDB Handling
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_pdb(pdb_id, output_dir="."):
    """Download a PDB file from RCSB. Returns path to downloaded file."""
    pdb_id = pdb_id.upper().strip()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{pdb_id}.pdb"
    if out.exists():
        logger.info(f"Already exists: {out}")
        return str(out)
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    run_cmd(f"wget -q -O {shlex.quote(str(out.resolve()))} {shlex.quote(url)}")
    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError(f"Failed to download PDB {pdb_id} — file too small or missing")
    # Validate ATOM records present
    content = out.read_text(errors='ignore')
    if 'ATOM' not in content and 'HETATM' not in content:
        raise RuntimeError(f"Downloaded file for {pdb_id} contains no ATOM records")
    logger.info(f"Downloaded {out} ({out.stat().st_size} bytes)")
    return str(out)


def inspect_pdb(pdb_file):
    """Analyze a PDB file and return structured information.
    The agent uses this to decide what preparation steps are needed."""
    info = {
        "file": str(pdb_file),
        "chains": set(), "residue_names": set(), "n_atoms": 0,
        "n_residues": 0, "n_waters": 0, "ligands": set(),
        "metals": set(), "disulfides": [], "missing_residues": [],
        "alt_locations": False, "has_hydrogens": False,
        "modified_residues": set(), "nucleic_acids": False,
    }
    nucleic = {"DA", "DT", "DG", "DC", "A", "U", "G", "C",
               "DA5", "DA3", "DT5", "DT3", "DG5", "DG3", "DC5", "DC3"}
    metals_set = {"ZN", "MG", "CA", "FE", "MN", "CO", "NI", "CU", "NA", "K"}
    standard_aa = STANDARD_AA
    seen_residues = set()

    with open(pdb_file) as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                info["n_atoms"] += 1
                chain = line[21].strip()
                resname = line[17:20].strip()
                resnum = line[22:26].strip()
                atomname = line[12:16].strip()
                reskey = f"{chain}:{resname}:{resnum}"

                if chain:
                    info["chains"].add(chain)
                if reskey not in seen_residues:
                    seen_residues.add(reskey)
                    info["n_residues"] += 1

                if len(line) > 16 and line[16] not in (' ', 'A', ''):
                    info["alt_locations"] = True
                if atomname.startswith("H") or atomname in ("1H", "2H", "3H"):
                    info["has_hydrogens"] = True

                if line.startswith("HETATM"):
                    if resname in ("HOH", "WAT"):
                        info["n_waters"] += 1
                    elif resname in metals_set:
                        info["metals"].add(resname)
                    elif resname not in standard_aa:
                        info["ligands"].add(resname)
                else:
                    if resname in nucleic:
                        info["nucleic_acids"] = True
                    elif resname not in standard_aa and resname not in nucleic:
                        info["modified_residues"].add(resname)

                info["residue_names"].add(resname)

            elif line.startswith("SSBOND"):
                info["disulfides"].append(line.strip())
            elif line.startswith("REMARK 465"):
                if len(line.strip()) > 20:
                    info["missing_residues"].append(line.strip())

    # --- REMARK 350: biological assembly ---
    biological_unit, biomt_ops = None, 0
    biomt_op_ids = set()
    biomt_target_chains = set()
    with open(pdb_file) as f:
        for line in f:
            if not line.startswith("REMARK 350"):
                continue
            payload = line[10:].strip()
            if "AUTHOR DETERMINED BIOLOGICAL UNIT" in payload:
                _, _, unit = payload.partition(":")
                biological_unit = unit.strip().upper() or biological_unit
            elif "APPLY THE FOLLOWING TO CHAINS" in payload:
                _, _, ch = payload.partition(":")
                for c in ch.replace(" ", "").split(","):
                    if c:
                        biomt_target_chains.add(c)
            elif payload.startswith("BIOMT1"):
                parts = payload.split()
                if len(parts) >= 2:
                    biomt_op_ids.add(parts[1])
    biomt_ops = len(biomt_op_ids)
    info["biological_unit"] = biological_unit
    info["biomt_operators"] = biomt_ops
    info["biomt_target_chains"] = sorted(biomt_target_chains)

    for key in ["chains", "ligands", "metals", "residue_names", "modified_residues"]:
        info[key] = sorted(info[key])
    info["n_disulfides"] = len(info["disulfides"])
    info["n_missing_residues"] = len(info["missing_residues"])
    return info


def clean_pdb(pdb_file, output_file=None, keep_waters=False, keep_hydrogens=False):
    """Clean a PDB using pdb4amber. Returns path to cleaned file."""
    pdb_file = Path(pdb_file)
    output_file = Path(output_file or pdb_file.with_name("clean.pdb"))

    flags = []
    if not keep_waters:
        flags.append("--dry")
    if not keep_hydrogens:
        flags.append("--reduce")
    flags.append("--no-conect")

    cmd = f"pdb4amber -i {pdb_file} -o {output_file} {' '.join(flags)}"
    result = run_cmd(cmd, check=False)

    if not output_file.exists():
        logger.warning("pdb4amber failed, doing manual cleanup")
        with open(pdb_file) as f:
            lines = f.readlines()
        with open(output_file, 'w') as f:
            for line in lines:
                if not keep_waters and line.startswith("HETATM") and line[17:20].strip() in ("HOH", "WAT"):
                    continue
                if len(line) > 16 and line[16] not in (' ', 'A', ''):
                    continue
                f.write(line)
        # Validate fallback output has ATOM records
        result_content = Path(output_file).read_text(errors='ignore') if Path(output_file).exists() else ""
        atom_count = sum(1 for l in result_content.splitlines() if l.startswith(('ATOM', 'HETATM')))
        if atom_count == 0:
            raise RuntimeError(f"clean_pdb fallback produced no ATOM records — input PDB may be malformed")

    return str(output_file)


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: File Writers — The agent tells these WHAT to write
# ═══════════════════════════════════════════════════════════════════════════════

def write_mdin(output_path, namelist_params, title="Generated by AmberMD Agent",
               extra_sections=None):
    """Write an Amber mdin file from a dictionary of &cntrl parameters.

    The agent decides parameters based on RAG + reasoning.
    This just formats the file.

    Args:
        output_path: Where to write the file
        namelist_params: Dict of &cntrl parameters
        title: Title line
        extra_sections: List of raw strings to append after &cntrl
            (for &wt, restraint definitions, umbrella windows, TI masks, etc.)
    """
    lines = [title, " &cntrl"]
    for key, val in namelist_params.items():
        if isinstance(val, str):
            lines.append(f"   {key}='{val}',")
        elif isinstance(val, bool):
            lines.append(f"   {key}={1 if val else 0},")
        elif isinstance(val, float):
            lines.append(f"   {key}={val},")
        else:
            lines.append(f"   {key}={val},")
    lines.append(" /")

    if extra_sections:
        for section in extra_sections:
            lines.append(section)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n")
    logger.info(f"Wrote mdin: {output_path}")
    return str(output_path)


def write_tleap(output_path, commands):
    """Write a tLEaP input file.
    commands: list of strings or a single multi-line string.
    """
    if isinstance(commands, list):
        content = "\n".join(commands)
    else:
        content = commands
    if "quit" not in content.lower():
        content = content.rstrip() + "\nquit\n"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(content)
    logger.info(f"Wrote tLEaP input: {output_path}")
    return str(output_path)


def write_cpptraj(output_path, commands):
    """Write a cpptraj input script."""
    if isinstance(commands, list):
        content = "\n".join(commands)
    else:
        content = commands
    if "run" not in content.lower():
        content = content.rstrip() + "\nrun\n"
    if "quit" not in content.lower():
        content = content.rstrip() + "\nquit\n"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(content)
    logger.info(f"Wrote cpptraj input: {output_path}")
    return str(output_path)


def write_groupfile(output_path, entries):
    """Write a groupfile for multi-simulation runs (REMD, TI, multi-sander).

    Args:
        entries: List of dicts with Amber flag mappings, e.g.:
            [{"mdin": "w0.mdin", "mdout": "w0.mdout", "prmtop": "sys.prmtop",
              "inpcrd": "w0.rst7", "rst": "w0_out.rst7", "mdcrd": "w0.nc"}]
    """
    flag_map = {
        "mdin": "-i", "mdout": "-o", "prmtop": "-p", "inpcrd": "-c",
        "rst": "-r", "mdcrd": "-x", "ref": "-ref", "inf": "-inf",
    }
    lines = []
    for entry in entries:
        parts = []
        for key, val in entry.items():
            flag = flag_map.get(key, f"-{key}")
            parts.append(f"{flag} {val}")
        lines.append(" ".join(parts))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n")
    logger.info(f"Wrote groupfile: {output_path} ({len(entries)} entries)")
    return str(output_path)


def write_file(output_path, content):
    """Generic file writer for anything the agent constructs:
    MMPBSA input, parmed scripts, custom configs, PBS/SLURM job scripts, etc."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(content)
    logger.info(f"Wrote: {output_path}")
    return str(output_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: Run Amber Programs — the agent decides WHICH tool & WHAT flags
# ═══════════════════════════════════════════════════════════════════════════════

def run_amber(engine, mdin, mdout, prmtop, inpcrd, rst_out, traj_out=None,
              ref=None, extra_flags="", cwd=None, timeout=None):
    """Run any Amber MD engine. Returns structured result for agent diagnosis."""
    parts = [engine, "-O",
             "-i", str(mdin), "-o", str(mdout),
             "-p", str(prmtop), "-c", str(inpcrd), "-r", str(rst_out)]
    if traj_out:
        parts.extend(["-x", str(traj_out)])
    if ref:
        parts.extend(["-ref", str(ref)])
    if extra_flags:
        # Caller responsible for quoting: extra_flags should be pre-validated agent input only
        parts.append(extra_flags)

    cmd = " ".join(parts)
    start = time.time()
    result = run_cmd(cmd, cwd=cwd, check=False, timeout=timeout)
    elapsed = time.time() - start

    rst_path = Path(cwd or ".") / rst_out if cwd else Path(rst_out)
    success = rst_path.exists()
    output = {
        "success": success,
        "elapsed_seconds": round(elapsed, 1),
        "return_code": result.returncode,
        "command": cmd,
    }
    if not success:
        mdout_path = Path(cwd or ".") / mdout if cwd else Path(mdout)
        if mdout_path.exists():
            output["error_tail"] = mdout_path.read_text(errors='ignore')[-2000:]
    return output


def run_tleap(input_file, cwd=None):
    """Run tLEaP. Returns output + leap.log for agent diagnosis."""
    result = run_cmd(f"tleap -f {shlex.quote(str(input_file))}", cwd=cwd, check=False)
    output = {
        "success": result.returncode == 0,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }
    log_file = Path(cwd or ".") / "leap.log"
    if log_file.exists():
        output["leap_log"] = log_file.read_text(errors='ignore')[-5000:]
    return output


def run_cpptraj(input_file, cwd=None):
    """Run cpptraj with an input file."""
    result = run_cmd(f"cpptraj -i {shlex.quote(str(input_file))}", cwd=cwd, check=False)
    return {
        "success": result.returncode == 0,
        "stdout": (result.stdout or "")[-3000:],
        "stderr": (result.stderr or "")[-2000:],
    }


def run_program(cmd_string, cwd=None, timeout=None):
    """Run ANY arbitrary command. Escape hatch for programs the agent
    discovers in the manual that aren't wrapped above (FEW.py, etc)."""
    result = run_cmd(cmd_string, cwd=cwd, check=False, timeout=timeout)
    return {
        "success": result.returncode == 0,
        "return_code": result.returncode,
        "stdout": (result.stdout or "")[-4000:],
        "stderr": (result.stderr or "")[-2000:],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: SLURM Job Submission & Monitoring
# ═══════════════════════════════════════════════════════════════════════════════

def write_slurm_script(output_path, commands, job_name="amber_md",
                        work_dir=None, partition=None, gpus=None,
                        walltime=None, extra_sbatch=None):
    """Write a SLURM job script for cluster submission.

    Cluster defaults (partition, GPU resources, walltime, environment setup)
    come verbatim from scripts/slurm_template.sh. Only override per-call when
    this specific job needs different resources.

    Args:
        output_path: Where to write the script
        commands: String or list of shell commands to run
        job_name: SLURM job name
        work_dir: Working directory on the cluster (-D flag)
        partition: Override partition from template
        gpus: Override GPU count (0 = CPU-only, removes --gres line)
        walltime: Override walltime from template (HH:MM:SS)
        extra_sbatch: List of additional raw #SBATCH lines to append
    """
    if isinstance(commands, list):
        cmd_block = "\n".join(commands)
    else:
        cmd_block = commands

    # Build SBATCH block: start from template, filter overridden directives
    exclude = set()
    override_lines = []
    if partition is not None:
        exclude.add("partition")
        override_lines.append(f"#SBATCH --partition={partition}")
    if walltime is not None:
        exclude.add("time")
        override_lines.append(f"#SBATCH --time={walltime}")
    if gpus is not None:
        exclude.add("gres")
        if gpus > 0:
            override_lines.append(f"#SBATCH --gres=gpu:{gpus}")

    sbatch_lines = _filter_sbatch(SLURM_CONFIG["sbatch_lines"], exclude) + override_lines

    lines = ["#!/bin/bash"]
    if work_dir:
        lines.append(f"#SBATCH -D {work_dir}")
    lines.append(f"#SBATCH --job-name={job_name}")
    lines.extend(sbatch_lines)
    lines.append(f"#SBATCH --output={job_name}_%j.out")
    lines.append(f"#SBATCH --error={job_name}_%j.err")
    if extra_sbatch:
        for sb in extra_sbatch:
            s = sb if sb.startswith("#SBATCH") else f"#SBATCH {sb}"
            lines.append(s)
    lines.append("")

    # Environment setup from template
    lines.extend(SLURM_CONFIG["env_lines"])
    lines.append("")

    # Job info
    lines.append('echo "Job started: $(date)"')
    lines.append('echo "Node: $(hostname)"')
    lines.append('echo "Directory: $(pwd)"')
    has_gpu = gpus is None or gpus > 0
    if has_gpu:
        lines.append("nvidia-smi || true")
    lines.append("")

    lines.append(cmd_block)
    lines.append("")
    lines.append('echo "Job finished: $(date)"')

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n")
    logger.info(f"Wrote SLURM script: {output_path}")
    return str(output_path)


def submit_slurm(script_path, cwd=None):
    """Submit a SLURM job script. Returns job ID."""
    result = run_cmd(f"sbatch {shlex.quote(str(script_path))}", cwd=cwd, check=False)
    output = {
        "success": result.returncode == 0,
        "stdout": result.stdout.strip() if result.stdout else "",
        "stderr": result.stderr.strip() if result.stderr else "",
    }
    # Parse job ID from "Submitted batch job 12345"
    if result.stdout:
        m = re.search(r'(\d+)', result.stdout)
        if m:
            output["job_id"] = int(m.group(1))
    return output


def check_slurm_job(job_id=None):
    """Check SLURM job status. If no job_id, shows all user's jobs."""
    if job_id:
        cmd = f"squeue -j {job_id} --format='%.10i %.20j %.8T %.10M %.6D %R'"
    else:
        cmd = "squeue -u $USER --format='%.10i %.20j %.8T %.10M %.6D %R'"
    result = run_cmd(cmd, check=False)
    return {
        "output": result.stdout.strip() if result.stdout else "No jobs found",
        "stderr": result.stderr.strip() if result.stderr else "",
    }


def cancel_slurm_job(job_id):
    """Cancel a SLURM job."""
    result = run_cmd(f"scancel {int(job_id)}", check=False)
    return {"success": result.returncode == 0}


def slurm_job_history(days=7):
    """Show recent completed jobs from sacct."""
    cmd = (f"sacct -u $USER --starttime=$(date -d '{int(days)} days ago' +%Y-%m-%d) "
           f"--format=JobID,JobName,State,Elapsed,MaxRSS,ExitCode,NodeList "
           f"--noheader")
    result = run_cmd(cmd, check=False)
    return {"output": result.stdout.strip() if result.stdout else "No history found"}


def write_slurm_array(output_path, command_template, array_range,
                       job_name="amber_array", work_dir=None,
                       partition=None, gpus=None, walltime=None):
    """Write a SLURM array job script.

    Cluster defaults come verbatim from scripts/slurm_template.sh.
    Perfect for umbrella sampling windows, TI lambda values, REMD replicas.

    Args:
        command_template: Command with {SLURM_ARRAY_TASK_ID} placeholder
            e.g., "cd window_{SLURM_ARRAY_TASK_ID} && pmemd.cuda -O -i md.mdin ..."
        array_range: SLURM array spec, e.g., "0-23" or "0-11%4" (max 4 concurrent)
        partition: Override partition from template
        gpus: Override GPU count (0 = CPU-only)
        walltime: Override walltime from template (HH:MM:SS)
    """
    exclude = set()
    override_lines = []
    if partition is not None:
        exclude.add("partition")
        override_lines.append(f"#SBATCH --partition={partition}")
    if walltime is not None:
        exclude.add("time")
        override_lines.append(f"#SBATCH --time={walltime}")
    if gpus is not None:
        exclude.add("gres")
        if gpus > 0:
            override_lines.append(f"#SBATCH --gres=gpu:{gpus}")

    sbatch_lines = _filter_sbatch(SLURM_CONFIG["sbatch_lines"], exclude) + override_lines

    lines = ["#!/bin/bash"]
    if work_dir:
        lines.append(f"#SBATCH -D {work_dir}")
    lines.append(f"#SBATCH --job-name={job_name}")
    lines.extend(sbatch_lines)
    lines.append(f"#SBATCH --array={array_range}")
    lines.append(f"#SBATCH --output={job_name}_%A_%a.out")
    lines.append(f"#SBATCH --error={job_name}_%A_%a.err")
    lines.append("")

    lines.extend(SLURM_CONFIG["env_lines"])
    lines.append("")

    lines.append('echo "Array task $SLURM_ARRAY_TASK_ID started: $(date)"')
    lines.append("")

    cmd = command_template.replace("{SLURM_ARRAY_TASK_ID}", "$SLURM_ARRAY_TASK_ID")
    lines.append(cmd)

    lines.append("")
    lines.append('echo "Array task $SLURM_ARRAY_TASK_ID finished: $(date)"')

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines) + "\n")
    logger.info(f"Wrote SLURM array script: {output_path} (array={array_range})")
    return str(output_path)


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: Output Readers — parse Amber outputs for agent reasoning
# ═══════════════════════════════════════════════════════════════════════════════

def read_mdout(mdout_file, last_n=None):
    """Parse energy data from an mdout file. Returns structured data."""
    records = []
    current = {}

    with open(mdout_file) as f:
        for line in f:
            m = re.match(r'\s*NSTEP\s+=\s+(\d+)\s+TIME.*=\s+([\d.]+)\s+TEMP.*=\s+([\d.]+)', line)
            if m:
                if current:
                    records.append(current)
                current = {
                    "NSTEP": int(m.group(1)),
                    "TIME": float(m.group(2)),
                    "TEMP": float(m.group(3)),
                }
                continue
            for term in ["Etot", "EKtot", "EPtot", "BOND", "ANGLE", "DIHED",
                         "VDWAALS", "EEL", "1-4 VDW", "1-4 EEL",
                         "EELEC", "EHBOND", "RESTRAINT",
                         "VOLUME", "DENSITY", "PRESS", "Density",
                         "DV/DL", "EAMBER"]:
                pattern = rf'{re.escape(term)}\s+=\s+([-\d.E+]+)'
                m2 = re.search(pattern, line)
                if m2 and current:
                    key = term.replace(" ", "_").replace("-", "_").replace("/", "_")
                    try:
                        current[key] = float(m2.group(1))
                    except ValueError:
                        pass
    if current:
        records.append(current)
    if last_n and len(records) > last_n:
        records = records[-last_n:]

    summary = {}
    if records:
        import numpy as np
        for key in records[0].keys():
            vals = [r.get(key) for r in records if key in r and r[key] is not None]
            if vals and key != "NSTEP":
                arr = np.array(vals, dtype=float)
                summary[key] = {
                    "mean": round(float(np.mean(arr)), 4),
                    "std": round(float(np.std(arr)), 4),
                    "min": round(float(np.min(arr)), 4),
                    "max": round(float(np.max(arr)), 4),
                }
    return {"n_records": len(records), "summary": summary, "records": records}


def read_file_tail(file_path, n_chars=3000):
    """Read the tail of any file for diagnosis."""
    p = Path(file_path)
    if not p.exists():
        return {"error": f"File not found: {file_path}"}
    content = p.read_text(errors='ignore')
    if len(content) > n_chars:
        return {"content": content[-n_chars:], "truncated": True, "total_size": len(content)}
    return {"content": content, "truncated": False, "total_size": len(content)}


def read_file_head(file_path, n_chars=3000):
    """Read the head of any file."""
    p = Path(file_path)
    if not p.exists():
        return {"error": f"File not found: {file_path}"}
    content = p.read_text(errors='ignore')
    if len(content) > n_chars:
        return {"content": content[:n_chars], "truncated": True, "total_size": len(content)}
    return {"content": content, "truncated": False, "total_size": len(content)}


def list_files(directory, pattern="*"):
    """List files matching a pattern. Helps agent discover outputs."""
    d = Path(directory)
    if not d.exists():
        return []
    files = sorted(d.glob(pattern))
    return [
        {"path": str(f), "name": f.name, "size": f.stat().st_size,
         "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()}
        for f in files if f.is_file()
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: RAG — Query the Amber Manual (Page-Indexed)
# ═══════════════════════════════════════════════════════════════════════════════

def rag_ingest(manual_path, index_output=None, append=False):
    """Ingest an Amber manual (PDF or text) into the page-level RAG index.
    Use --append to add multiple documents to the same index."""
    sys.path.insert(0, str(BASE_DIR))
    from scripts.rag_amber import PageIndex
    index_output = index_output or str(REFERENCES_DIR / "amber_index.json")
    Path(index_output).parent.mkdir(parents=True, exist_ok=True)

    index = PageIndex()
    if append and Path(index_output).exists():
        index.load(index_output)
    index.ingest(manual_path)
    index.save(index_output)
    _rag_index_cache.pop(index_output, None)  # invalidate cache after new ingest
    return {"pages": index.n_pages, "index_path": index_output,
            "toc_entries": len(index.toc), "stats": index.stats()}


def _get_rag_index(index_path):
    """Load RAG index from cache or disk. Returns (index, None) or (None, error_dict)."""
    sys.path.insert(0, str(BASE_DIR))
    from scripts.rag_amber import PageIndex
    index_path = index_path or str(REFERENCES_DIR / "amber_index.json")
    if not Path(index_path).exists():
        return None, {"error": "No Amber manual index found.",
                      "hint": "Run: python md_agent.py rag-ingest <manual.pdf>"}
    if index_path not in _rag_index_cache:
        index = PageIndex()
        index.load(index_path)
        _rag_index_cache[index_path] = index
    return _rag_index_cache[index_path], None


def rag_query(question, top_k=5, index_path=None):
    """Query the Amber manual — returns FULL PAGES for the agent to read.

    THIS IS THE AGENT'S PRIMARY LEARNING MECHANISM.
    Pages preserve full semantic context: examples, parameter tables,
    warnings, and surrounding discussion — exactly as the author wrote them.
    The LLM (Claude Code) does the semantic understanding.
    """
    index_path = index_path or str(REFERENCES_DIR / "amber_index.json")
    index, err = _get_rag_index(index_path)
    if err:
        return err
    results = index.query(question, top_k=top_k)
    return {"question": question, "n_results": len(results), "results": results}


def rag_section(section_name, index_path=None):
    """Get all pages belonging to a named section of the manual."""
    index_path = index_path or str(REFERENCES_DIR / "amber_index.json")
    index, err = _get_rag_index(index_path)
    if err:
        return err
    return index.query_by_section(section_name)


def rag_page(page_num, index_path=None):
    """Get a specific page from the manual by page number."""
    index_path = index_path or str(REFERENCES_DIR / "amber_index.json")
    index, err = _get_rag_index(index_path)
    if err:
        return err
    return index.get_page(page_num)


def rag_pages(start, end, index_path=None):
    """Get a range of pages from the manual."""
    index_path = index_path or str(REFERENCES_DIR / "amber_index.json")
    index, err = _get_rag_index(index_path)
    if err:
        return err
    return index.get_page_range(start, end)


def rag_toc(index_path=None):
    """Get the table of contents detected from the manual."""
    index_path = index_path or str(REFERENCES_DIR / "amber_index.json")
    index, err = _get_rag_index(index_path)
    if err:
        return err
    return {"toc": index.get_toc(), "stats": index.stats()}


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: Plotting
# ═══════════════════════════════════════════════════════════════════════════════

def plot_timeseries(data_file, output_png, xlabel="Time", ylabel="Value",
                    title=None, column_x=0, column_y=1, time_scale=1.0):
    """Plot a time series from a data file."""
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np

        data = np.loadtxt(data_file, comments=['#', '@'])
        x = (data[:, column_x] if data.ndim > 1 else np.arange(len(data))) * time_scale
        y = data[:, column_y] if data.ndim > 1 else data

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x, y, linewidth=0.4, alpha=0.7)
        if len(y) > 100:
            window = max(len(y) // 100, 5)
            rolling = np.convolve(y, np.ones(window)/window, mode='valid')
            ax.plot(x[:len(rolling)], rolling, 'k-', linewidth=1.5, label='Running avg')
            ax.legend()
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        ax.set_title(title or Path(data_file).stem)
        plt.tight_layout(); plt.savefig(output_png, dpi=150); plt.close()
        return {"success": True, "plot": str(output_png)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def plot_bar(data_file, output_png, xlabel="Residue", ylabel="Value",
             title=None, column_x=0, column_y=1):
    """Plot a bar chart."""
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np

        data = np.loadtxt(data_file, comments=['#', '@'])
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(data[:, column_x], data[:, column_y], width=1.0, color='steelblue')
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        ax.set_title(title or Path(data_file).stem)
        plt.tight_layout(); plt.savefig(output_png, dpi=150); plt.close()
        return {"success": True, "plot": str(output_png)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL: Convergence Check
# ═══════════════════════════════════════════════════════════════════════════════

def check_convergence(data_file, column=1, abs_threshold=0.5):
    """Assess convergence of a time series.

    Primary convergence criterion: absolute drift |mean(second half) - mean(first half)| < abs_threshold.
    Default threshold 0.5 Å is the skill standard for RMSD plateaus. Override for
    other observables (e.g. temperature → 5 K, density → 0.02 g/cc).
    Agent uses this to decide if more simulation is needed.
    """
    try:
        import numpy as np
        data = np.loadtxt(data_file, comments=['#', '@'])
        values = data[:, column] if data.ndim > 1 else data
        n = len(values)
        if n < 50:
            return {"status": "insufficient_data", "n_points": n}

        mean = float(np.mean(values))
        std = float(np.std(values))
        half1 = float(np.mean(values[:n//2]))
        half2 = float(np.mean(values[n//2:]))
        drift_abs = abs(half2 - half1)
        drift_pct = (drift_abs / abs(mean) * 100) if mean != 0 else float('inf')

        block_sems = []
        for bs in [1, 5, 10, 50, 100, 500]:
            if bs > n // 4:
                break
            nblocks = n // bs
            block_means = [float(np.mean(values[i*bs:(i+1)*bs])) for i in range(nblocks)]
            sem = float(np.std(block_means) / np.sqrt(nblocks))
            block_sems.append({"block_size": bs, "sem": round(sem, 6)})

        return {
            "status": "converged" if drift_abs < abs_threshold else "not_converged",
            "criterion": f"|drift_abs| < {abs_threshold} (units of input)",
            "n_points": n, "mean": round(mean, 4), "std": round(std, 4),
            "first_half_mean": round(half1, 4), "second_half_mean": round(half2, 4),
            "drift_abs": round(drift_abs, 4), "drift_pct_info_only": round(drift_pct, 2),
            "block_averaging": block_sems,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  Pre-flight & Validation (Optimization Layer)
# ═══════════════════════════════════════════════════════════════════════════════

def preflight(pdb_file, check_ligands=True):
    """Pre-flight inspection of a PDB before system building.

    Runs all the checks that would otherwise be discovered at runtime:
    - Truncated termini (first resid != 1 → needs capping)
    - Missing H atoms on ligands (crystal PDB → need PubChem SDF)
    - Chain breaks (gap in residue numbering → tLEaP will warn)
    - Modified residues (e.g., TPO, SEP → need conversion)
    - Missing residues (REMARK 465 entries)
    - Disulfide bonds (need CYX in tLEaP)
    - Ligand identification and H-atom status

    Returns a structured report with PASS/WARN/FAIL for each check
    and recommended actions.
    """
    info = inspect_pdb(pdb_file)
    report = {
        "file": str(pdb_file),
        "summary": "PASS",
        "checks": [],
        "actions_required": [],
    }

    standard_aa = STANDARD_AA
    # Known modified residues that need conversion
    mod_res_fixes = {
        "TPO": "THR (remove P, O1P, O2P, O3P)",
        "SEP": "SER (remove P, O1P, O2P, O3P)",
        "PTR": "TYR (remove P, O1P, O2P, O3P)",
        "MLY": "LYS (methylated lysine)",
        "MSE": "MET (selenomethionine → replace SE with SD)",
    }

    # --- Check 1: Truncated termini ---
    chain_termini = {}
    with open(pdb_file) as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                chain = line[21].strip()
                resname = line[17:20].strip()
                try:
                    resnum = int(line[22:26].strip())
                except ValueError:
                    continue
                if resname in standard_aa and chain:
                    if chain not in chain_termini:
                        chain_termini[chain] = {"first": resnum, "last": resnum,
                                                 "first_name": resname, "last_name": resname}
                    chain_termini[chain]["last"] = resnum
                    chain_termini[chain]["last_name"] = resname

    needs_capping = False
    already_capped = False
    for chain, term in chain_termini.items():
        has_ace = term["first_name"] == "ACE"
        has_nme = term["last_name"] == "NME"
        if has_ace or has_nme:
            already_capped = True
            report["checks"].append({
                "check": f"termini_{chain}",
                "status": "PASS",
                "detail": f"Chain {chain}: already capped ({'ACE' if has_ace else ''}{'/' if has_ace and has_nme else ''}{'NME' if has_nme else ''}) — no capping needed",
            })
        elif term["first"] > 1:
            needs_capping = True
            report["checks"].append({
                "check": f"termini_{chain}",
                "status": "WARN",
                "detail": f"Chain {chain}: starts at residue {term['first']} ({term['first_name']}) — truncated construct, needs ACE/NME caps",
            })

    if needs_capping:
        report["actions_required"].append(
            "RUN: python scripts/cap_protein.py <input.pdb> <output_capped.pdb>"
        )
    elif chain_termini and not already_capped:
        report["checks"].append({
            "check": "termini",
            "status": "PASS",
            "detail": "All chains start at residue 1 — full-length, no capping needed",
        })

    # --- Check 2: Chain breaks (gaps in residue numbering) ---
    chain_resnums = {}
    with open(pdb_file) as f:
        for line in f:
            if line.startswith("ATOM"):
                chain = line[21].strip()
                try:
                    resnum = int(line[22:26].strip())
                except ValueError:
                    continue
                if chain not in chain_resnums:
                    chain_resnums[chain] = set()
                chain_resnums[chain].add(resnum)

    breaks_found = []
    for chain, resnums in chain_resnums.items():
        sorted_res = sorted(resnums)
        for i in range(1, len(sorted_res)):
            gap = sorted_res[i] - sorted_res[i-1]
            if gap > 1:
                breaks_found.append({
                    "chain": chain,
                    "from": sorted_res[i-1],
                    "to": sorted_res[i],
                    "missing": gap - 1,
                    "chain_length": len(sorted_res),
                })

    if breaks_found:
        detail_strs = [
            f"Chain {b['chain']}: gap {b['from']}→{b['to']} ({b['missing']} missing residues)"
            for b in breaks_found
        ]
        report["checks"].append({
            "check": "chain_breaks",
            "status": "FAIL",
            "detail": f"{len(breaks_found)} mid-chain break(s) — unusable for MD without loop fill",
            "breaks": detail_strs,
        })
        report["summary"] = "FAIL — fix required before system building"
        for b in breaks_found:
            length = b["chain_length"]
            if length <= 400:
                action = (
                    f"Chain {b['chain']} break {b['from']}→{b['to']}: "
                    f"PREFERRED: find another PDB without this break (search with resolution_max=2.5). "
                    f"FALLBACK: chain length {length} AA ≤ 400 — ESMFold public API can predict "
                    f"full structure (https://esmatlas.com/resources?action=fold). "
                    f"Submit full chain FASTA. Use predicted structure instead of this PDB."
                )
            else:
                action = (
                    f"Chain {b['chain']} break {b['from']}→{b['to']}: "
                    f"PREFERRED: find another PDB without this break (search with resolution_max=2.5). "
                    f"Chain length {length} AA > 400 — ESMFold public API cannot handle this length. "
                    f"Cannot auto-fix. Ask user to provide a complete structure or identify a "
                    f"different crystal structure without this gap."
                )
            report["actions_required"].append(action)
    else:
        report["checks"].append({"check": "chain_breaks", "status": "PASS", "detail": "No chain breaks"})

    # --- Check 3: Modified residues ---
    mods_needing_fix = {}
    for mod in info.get("modified_residues", []):
        if mod in mod_res_fixes:
            mods_needing_fix[mod] = mod_res_fixes[mod]

    if mods_needing_fix:
        report["checks"].append({
            "check": "modified_residues",
            "status": "WARN",
            "detail": f"Modified residues need conversion: {mods_needing_fix}",
        })
        for mod, fix in mods_needing_fix.items():
            report["actions_required"].append(f"CONVERT: {mod} → {fix} (remove extra atoms, rename residue)")
        report["summary"] = "WARN"
    else:
        report["checks"].append({"check": "modified_residues", "status": "PASS", "detail": "No problematic modified residues"})

    # --- Check 4: Ligands and H atoms ---
    # Exclude caps, modified residues, waters, ions, and common non-drug HETATM
    non_drug_hetatm = {
        # caps / termini
        "ACE", "NME", "NMA", "FOR", "NH2",
        # waters
        "HOH", "WAT", "TIP", "DOD",
        # ions (PDB codes and element symbols)
        "NA", "CL", "K", "MG", "CA", "ZN", "FE", "MN", "NI", "CU", "CO",
        "Na+", "Cl-", "K+", "Mg2+", "ZN2", "FE2", "FE3",
        "IOD", "BR", "F",
        # modified AA (handled in check 3)
        "TPO", "SEP", "PTR", "MLY", "MSE", "CSO", "CME", "OCS",
        # common crystallographic additives / cryo-protectants
        "GOL", "EDO", "PEG", "PE4", "PE5", "1PE", "2PE", "P6G",
        "MPD", "IPA", "EOH", "MOH", "EGL",
        # buffers / precipitants
        "SO4", "PO4", "ACT", "TRS", "MES", "EPE", "HEZ", "IMD", "TLA",
        "MLI", "CIT", "TAR", "FMT", "AZI", "SCN", "NO3",
        # reducing agents / additives
        "DMS", "BME", "DTT", "TCE",
        # glycerol/detergent fragments common in crystal contacts
        "PGE", "PGO", "BOG", "LMT", "LMU", "DIO", "XPE",
    }
    real_ligands = [lig for lig in info.get("ligands", []) if lig not in non_drug_hetatm]

    if check_ligands and real_ligands:
        # Check if ANY ligand atom has H
        ligand_h_status = {}
        with open(pdb_file) as f:
            for line in f:
                if line.startswith("HETATM"):
                    resname = line[17:20].strip()
                    atomname = line[12:16].strip()
                    if resname in real_ligands:
                        if resname not in ligand_h_status:
                            ligand_h_status[resname] = {"total": 0, "h_atoms": 0}
                        ligand_h_status[resname]["total"] += 1
                        if atomname.startswith("H") or atomname in ("1H", "2H", "3H"):
                            ligand_h_status[resname]["h_atoms"] += 1

        for lig, counts in ligand_h_status.items():
            if counts["h_atoms"] == 0:
                report["checks"].append({
                    "check": f"ligand_{lig}",
                    "status": "FAIL",
                    "detail": f"Ligand {lig}: {counts['total']} atoms, 0 hydrogens — crystal PDB, cannot use directly for antechamber",
                })
                report["actions_required"].append(
                    f"LIGAND {lig}: Follow skills/amber-ligand.md Branch C — "
                    f"(1) fetch CCD ideal SDF by residue name, "
                    f"(2) cross-validate with PubChem formula/charge, "
                    f"(3) extract crystal HETATM (one chain), "
                    f"(4) MCS coord-transplant from crystal → AddHs, "
                    f"(5) antechamber GAFF2. NEVER use crystal PDB directly. NEVER use get_3d_conformer + rigid align (3.48 Å RMSD error)."
                )
                report["summary"] = "FAIL"
            else:
                report["checks"].append({
                    "check": f"ligand_{lig}",
                    "status": "PASS",
                    "detail": f"Ligand {lig}: {counts['total']} atoms, {counts['h_atoms']} hydrogens — has H, can parametrize",
                })
    elif not real_ligands:
        report["checks"].append({"check": "ligands", "status": "PASS", "detail": "No drug-like ligands detected (protein-only or only buffer/ion HETATM)"})

    # --- Check 5: Missing residues (REMARK 465) — classify terminal vs internal ---
    if info.get("missing_residues"):
        missing_per_chain = {}
        for line in info["missing_residues"]:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    ch = parts[3]
                    rn = int(parts[4])
                    missing_per_chain.setdefault(ch, []).append(rn)
                except (ValueError, IndexError):
                    continue
        terminal_count, internal_count, internal_detail = 0, 0, []
        for ch, missing_rns in missing_per_chain.items():
            present = sorted(chain_resnums.get(ch, set()))
            if not present:
                terminal_count += len(missing_rns)
                continue
            lo, hi = present[0], present[-1]
            for rn in missing_rns:
                if rn < lo or rn > hi:
                    terminal_count += 1
                else:
                    internal_count += 1
                    internal_detail.append(f"{ch}:{rn}")
        if internal_count > 0:
            report["checks"].append({
                "check": "missing_residues",
                "status": "FAIL",
                "detail": f"{internal_count} INTERNAL missing residue(s) ({', '.join(internal_detail[:10])}) — loop modeling required; "
                          f"{terminal_count} terminal missing — capping handles",
            })
            report["summary"] = "FAIL — fix required before system building"
            report["actions_required"].append(
                "Internal missing residues require loop modeling: python scripts/loop_model.py "
                "(AlphaFold/ESMFold + graft). See skills/amber-protein-prep.md."
            )
        elif terminal_count > 0:
            report["checks"].append({
                "check": "missing_residues",
                "status": "WARN",
                "detail": f"{terminal_count} terminal missing residue(s) — ACE/NME capping handles. No loop modeling needed.",
            })
        else:
            report["checks"].append({
                "check": "missing_residues",
                "status": "WARN",
                "detail": f"{info['n_missing_residues']} REMARK 465 entries (chain assignment unclear) — inspect manually",
            })
    else:
        report["checks"].append({"check": "missing_residues", "status": "PASS", "detail": "No REMARK 465 missing residues"})

    # --- Check 6: Disulfide bonds ---
    if info.get("disulfides"):
        report["checks"].append({
            "check": "disulfides",
            "status": "WARN",
            "detail": f"{info['n_disulfides']} disulfide bond(s) — ensure CYS→CYX in tLEaP or use 'bond' command",
        })
        report["actions_required"].append(
            "DISULFIDES: Verify tLEaP recognizes them (check leap.log for 'Added missing bond'). If not, add explicit 'bond' commands."
        )
    else:
        report["checks"].append({"check": "disulfides", "status": "PASS", "detail": "No disulfide bonds"})

    # --- Check 7: Alt locations ---
    if info.get("alt_locations"):
        report["checks"].append({
            "check": "alt_locations",
            "status": "WARN",
            "detail": "Alternate locations present — pdb4amber will keep only 'A' conformer",
        })
    else:
        report["checks"].append({"check": "alt_locations", "status": "PASS", "detail": "No alternate locations"})

    # --- Check 8: Biological assembly (REMARK 350) ---
    bio_unit = info.get("biological_unit")
    biomt_ops = info.get("biomt_operators", 0)
    n_chains = len(info.get("chains", []))
    oligomer_count = {
        "MONOMERIC": 1, "DIMERIC": 2, "TRIMERIC": 3, "TETRAMERIC": 4,
        "PENTAMERIC": 5, "HEXAMERIC": 6, "HEPTAMERIC": 7, "OCTAMERIC": 8,
    }
    expected_chains = None
    if bio_unit:
        for key, n in oligomer_count.items():
            if key in bio_unit:
                expected_chains = n * max(1, len(info.get("biomt_target_chains", []) or [None]))
                break
    if expected_chains is None and biomt_ops > 1:
        expected_chains = biomt_ops * max(1, len(info.get("biomt_target_chains", []) or [None]))
    if expected_chains and expected_chains > n_chains:
        report["checks"].append({
            "check": "biological_assembly",
            "status": "FAIL",
            "detail": (
                f"Asymmetric unit has {n_chains} chain(s) but REMARK 350 says biological unit "
                f"is {bio_unit or '(implied multimer from BIOMT)'} ({biomt_ops} operators, "
                f"expected ~{expected_chains} chains). Active site may sit at chain interface — "
                f"naive simulation of asymmetric unit will be WRONG."
            ),
        })
        report["actions_required"].append(
            "Generate biological assembly: download <PDBID>-assembly1.pdb from RCSB "
            "(https://files.rcsb.org/download/<PDBID>-assembly1.pdb) OR apply REMARK 350 "
            "BIOMT operators with a script (numpy: new_xyz = R @ xyz + T for each operator)."
        )
    elif biomt_ops > 0:
        report["checks"].append({
            "check": "biological_assembly",
            "status": "PASS",
            "detail": f"Asymmetric unit chains ({n_chains}) match biological unit "
                      f"({bio_unit or 'see BIOMT'}, {biomt_ops} operator(s))",
        })
    else:
        report["checks"].append({
            "check": "biological_assembly",
            "status": "INFO",
            "detail": "No REMARK 350 biological assembly information",
        })

    # --- Overall summary ---
    statuses = [c["status"] for c in report["checks"]]
    if "FAIL" in statuses:
        report["summary"] = "FAIL — fix required before system building"
    elif "WARN" in statuses:
        report["summary"] = "WARN — review actions before proceeding"
    else:
        report["summary"] = "PASS — ready for system building"

    report["system_info"] = {
        "n_atoms": info["n_atoms"],
        "n_residues": info["n_residues"],
        "chains": info["chains"],
        "ligands": info["ligands"],
        "metals": info["metals"],
        "n_waters": info["n_waters"],
    }

    return report


def validate_step(mdout_file, expected_nstep=None, min_density=None,
                   max_density=None, check_rst7=None, target_temp=300.0,
                   temp_tolerance=10.0):
    """Validate an MD simulation step completed successfully.

    This is the GATE between pipeline steps. Call after every pmemd/sander run
    before proceeding to the next step. Returns PASS/FAIL with diagnostics.

    Args:
        mdout_file: Path to the .mdout file
        expected_nstep: Expected final NSTEP value (e.g. 1250000)
        min_density: Minimum acceptable density (e.g. 0.95 for equil)
        max_density: Maximum acceptable density (e.g. 1.1)
        check_rst7: Path to rst7 file that should exist
    """
    result = {
        "file": str(mdout_file),
        "status": "PASS",
        "checks": [],
        "diagnostics": {},
    }

    if not Path(mdout_file).exists():
        return {"file": str(mdout_file), "status": "FAIL",
                "checks": [{"check": "file_exists", "status": "FAIL", "detail": "mdout file not found"}]}

    content = ""
    with open(mdout_file, 'rb') as f:
        f.seek(0, 2)  # end
        size = f.tell()
        f.seek(max(0, size - 102400))  # last 100KB
        content = f.read().decode('utf-8', errors='ignore')

    # --- Check 1: FATAL errors ---
    fatal_patterns = [
        r"FATAL",
        r"Calculation halted",
        r"NaN",
        r"SHAKE failure",
        r"Periodic box dimensions have changed too much",
        r"vlimit exceeded",
        r"cudaGetDeviceCount failed",
    ]
    errors_found = []
    for pat in fatal_patterns:
        matches = re.findall(pat, content)
        if matches:
            errors_found.append(f"{pat} (x{len(matches)})")

    if errors_found:
        result["checks"].append({
            "check": "fatal_errors",
            "status": "FAIL",
            "detail": f"Fatal errors found: {', '.join(errors_found)}",
        })
        result["status"] = "FAIL"
    else:
        result["checks"].append({"check": "fatal_errors", "status": "PASS", "detail": "No fatal errors"})

    # --- Check 2: Final NSTEP ---
    nstep_matches = re.findall(r'NSTEP\s+=\s+(\d+)', content)
    if nstep_matches:
        final_nstep = int(nstep_matches[-1])
        result["diagnostics"]["final_nstep"] = final_nstep
        if expected_nstep is not None:
            if final_nstep >= expected_nstep:
                result["checks"].append({
                    "check": "nstep_reached",
                    "status": "PASS",
                    "detail": f"Final NSTEP={final_nstep} >= expected {expected_nstep}",
                })
            else:
                result["checks"].append({
                    "check": "nstep_reached",
                    "status": "FAIL",
                    "detail": f"Final NSTEP={final_nstep} < expected {expected_nstep} — simulation incomplete",
                })
                result["status"] = "FAIL"
    else:
        result["checks"].append({
            "check": "nstep_reached",
            "status": "FAIL",
            "detail": "No NSTEP entries found in mdout — simulation may not have started",
        })
        result["status"] = "FAIL"

    # --- Check 3: Density ---
    density_matches = re.findall(r'Density\s+=\s+([\d.]+)', content)
    if density_matches:
        # Filter out the very last entry which can be zero (final energy decomposition)
        densities = [float(d) for d in density_matches if float(d) > 0.01]
        if densities:
            final_density = densities[-1]
            result["diagnostics"]["final_density"] = final_density
            result["diagnostics"]["density_range"] = [min(densities), max(densities)]

            density_ok = True
            if min_density is not None and final_density < min_density:
                density_ok = False
                result["checks"].append({
                    "check": "density",
                    "status": "FAIL",
                    "detail": f"Final density {final_density:.4f} < minimum {min_density} — box not equilibrated. Add unrestrained equil2 with barostat=1, taup=0.5, ntwr=500.",
                })
                result["status"] = "FAIL"
            if max_density is not None and final_density > max_density:
                density_ok = False
                result["checks"].append({
                    "check": "density",
                    "status": "FAIL",
                    "detail": f"Final density {final_density:.4f} > maximum {max_density} — possible system collapse",
                })
                result["status"] = "FAIL"
            if density_ok:
                result["checks"].append({
                    "check": "density",
                    "status": "PASS",
                    "detail": f"Final density {final_density:.4f} g/cc — within acceptable range",
                })
    else:
        result["checks"].append({
            "check": "density",
            "status": "INFO",
            "detail": "No density data (NVT run or minimization)",
        })

    # --- Check 4: Temperature stability ---
    # Stop parsing at AVERAGES section to avoid RMS FLUCTUATIONS temps (which are ~0-10 K)
    averages_idx = content.find("A V E R A G E S")
    content_before_averages = content[:averages_idx] if averages_idx >= 0 else content
    temp_matches = re.findall(r'TEMP\(K\)\s+=\s+([\d.]+)', content_before_averages)
    if temp_matches:
        temps = [float(t) for t in temp_matches]
        # Check last 20% of temps for stability
        late_temps = temps[int(len(temps)*0.8):]
        if late_temps:
            avg_temp = sum(late_temps) / len(late_temps)
            result["diagnostics"]["final_temp"] = round(avg_temp, 2)
            if avg_temp < 1.0:  # minimization
                result["checks"].append({"check": "temperature", "status": "INFO", "detail": "Minimization (TEMP≈0)"})
            elif abs(avg_temp - target_temp) > 2 * temp_tolerance and avg_temp > 10:
                result["checks"].append({
                    "check": "temperature",
                    "status": "FAIL",
                    "detail": f"Average temperature {avg_temp:.1f} K deviates from target {target_temp:.1f} K by > {2*temp_tolerance:.0f} K — system not thermally equilibrated",
                })
                result["status"] = "FAIL"
            elif abs(avg_temp - target_temp) > temp_tolerance and avg_temp > 10:
                result["checks"].append({
                    "check": "temperature",
                    "status": "WARN",
                    "detail": f"Average temperature {avg_temp:.1f} K deviates from target {target_temp:.1f} K by > {temp_tolerance:.0f} K — extend equilibration before production",
                })
            else:
                result["checks"].append({
                    "check": "temperature",
                    "status": "PASS",
                    "detail": f"Temperature stable at {avg_temp:.1f} K (target {target_temp:.0f} ±{temp_tolerance:.0f})",
                })

    # --- Check 5: rst7 file exists ---
    if check_rst7:
        rst_path = Path(check_rst7)
        if rst_path.exists() and rst_path.stat().st_size > 0:
            result["checks"].append({
                "check": "rst7_exists",
                "status": "PASS",
                "detail": f"Restart file exists: {rst_path.name} ({rst_path.stat().st_size/1024:.0f} KB)",
            })
        else:
            result["checks"].append({
                "check": "rst7_exists",
                "status": "FAIL",
                "detail": f"Restart file missing or empty: {check_rst7}",
            })
            result["status"] = "FAIL"

    # --- Check 6: Energy sanity (no huge values) ---
    etot_matches = re.findall(r'Etot\s+=\s+([-\d.E+]+)', content)
    if etot_matches:
        try:
            etots = [float(e) for e in etot_matches[-10:]]  # last 10 values
            result["diagnostics"]["final_etot"] = etots[-1]
            if any(abs(e) > 1e8 for e in etots):
                result["checks"].append({
                    "check": "energy_sanity",
                    "status": "FAIL",
                    "detail": f"Extreme energy values detected (|Etot| > 1e8) — system may have exploded",
                })
                result["status"] = "FAIL"
            elif any("nan" in str(e).lower() for e in etots):
                result["checks"].append({
                    "check": "energy_sanity",
                    "status": "FAIL",
                    "detail": "NaN in energy — simulation crashed",
                })
                result["status"] = "FAIL"
            else:
                result["checks"].append({
                    "check": "energy_sanity",
                    "status": "PASS",
                    "detail": f"Energy reasonable (Etot={etots[-1]:.1f} kcal/mol)",
                })
        except (ValueError, IndexError):
            pass

    return result


def validate_tleap(log_file):
    """Validate a tLEaP log file. Returns structured pass/fail report."""
    result = {
        "file": str(log_file),
        "status": "PASS",
        "checks": [],
        "warnings_summary": {},
    }

    if not Path(log_file).exists():
        return {"file": str(log_file), "status": "FAIL",
                "checks": [{"check": "file_exists", "status": "FAIL", "detail": "Log file not found"}]}

    content = Path(log_file).read_text()

    # Check exit line
    exit_match = re.findall(r'Exiting LEaP: Errors = (\d+); Warnings = (\d+)', content)
    if exit_match:
        errors, warnings = int(exit_match[-1][0]), int(exit_match[-1][1])
        result["diagnostics"] = {"errors": errors, "warnings": warnings}

        if errors > 0:
            result["checks"].append({
                "check": "tleap_errors",
                "status": "FAIL",
                "detail": f"tLEaP exited with {errors} error(s)",
            })
            result["status"] = "FAIL"
        else:
            result["checks"].append({
                "check": "tleap_errors",
                "status": "PASS",
                "detail": f"tLEaP: Errors=0, Warnings={warnings}",
            })

        # Categorize warnings
        long_bonds = re.findall(r'bond of ([\d.]+) angstroms between .* atoms:\n-------\s+(.+)', content)
        close_contacts = re.findall(r'Close contact of ([\d.]+) angstroms between', content)

        _std_res = STANDARD_AA | {"HOH", "WAT", "NA", "CL", "K", "MG", "CA", "ZN", "FE", "MN", "NI", "CU"}
        ligand_bond_warnings = []
        protein_bond_warnings = []
        for dist, atoms in long_bonds:
            tokens = re.findall(r'\b([A-Z0-9]{2,4})\b', atoms)
            is_ligand = any(t not in _std_res for t in tokens if len(t) >= 2)
            if is_ligand:
                ligand_bond_warnings.append(f"{dist}Å: {atoms.strip()}")
            else:
                protein_bond_warnings.append(f"{dist}Å: {atoms.strip()}")

        result["warnings_summary"] = {
            "long_bonds_protein": len(protein_bond_warnings),
            "long_bonds_ligand": len(ligand_bond_warnings),
            "close_contacts": len(close_contacts),
        }

        if ligand_bond_warnings:
            result["checks"].append({
                "check": "ligand_bonds",
                "status": "FAIL",
                "detail": f"{len(ligand_bond_warnings)} ligand bond warnings — ligand coordinates may be wrong. Check mol2 file.",
                "examples": ligand_bond_warnings[:5],
            })
            result["status"] = "FAIL"

        if protein_bond_warnings:
            result["checks"].append({
                "check": "protein_bonds",
                "status": "WARN",
                "detail": f"{len(protein_bond_warnings)} protein long-bond warnings — likely chain breaks (benign)",
            })

        if close_contacts:
            result["checks"].append({
                "check": "close_contacts",
                "status": "WARN",
                "detail": f"{len(close_contacts)} close contacts — will be resolved by minimization",
            })
    else:
        result["checks"].append({
            "check": "tleap_exit",
            "status": "FAIL",
            "detail": "No 'Exiting LEaP' line found — tLEaP may have crashed",
        })
        result["status"] = "FAIL"

    # Check for fatal patterns
    fatal_patterns = ["Could not open file", "Could not find atom type",
                       "Could not find bond parameter", "Fatal Error"]
    for pat in fatal_patterns:
        if pat in content:
            result["checks"].append({
                "check": "fatal_pattern",
                "status": "FAIL",
                "detail": f"Found '{pat}' in tLEaP log",
            })
            result["status"] = "FAIL"

    return result


def generate_equil_density_script(output_path, prmtop, rst_in, rst_out,
                                    mdin_path, work_dir, job_name="equil_density",
                                    prod_mdin=None, prod_mdout=None,
                                    prod_rst=None, prod_nc=None,
                                    max_iter=30, target_density=1.00,
                                    density_tolerance=0.05,
                                    density_fluct_max=0.02,
                                    temperature=300.0):
    """Generate a SLURM script with pmemd.cuda restart loop for density convergence.

    Convergence criteria (both must hold):
      |mean(density last 5 frames) - target_density| <= density_tolerance
      max(density last 5 frames) - min(...) < density_fluct_max

    Default: target=1.00 g/cc, ±0.05 (so range 0.95–1.05), fluctuation < 0.02.
    Density is parsed from the time-series Density lines only — averages and
    RMS-fluctuation sections are explicitly excluded by a python helper.
    """
    mdin_dir = Path(mdin_path)
    if mdin_dir.suffix:
        mdin_dir = mdin_dir.parent
    mdin_dir.mkdir(parents=True, exist_ok=True)
    burst_mdin = mdin_dir / "equil_density_burst.mdin"
    burst_mdin_content = f"""Equil density burst - 10 ps NPT with Berendsen barostat
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=5000, dt=0.002,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=1.0,
  temp0={temperature:.1f},
  ntp=1, barostat=1, pres0=1.0, taup=0.5,
  ntpr=500, ntwx=0, ntwr=500,
  ioutfm=1,
  ntr=0,
  ig=-1,
  cut=10.0,
 /

"""
    burst_mdin.write_text(burst_mdin_content)

    # Build SLURM script
    script_lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name={job_name}",
    ]

    # Add template SBATCH lines
    sbatch_lines = _filter_sbatch(SLURM_CONFIG["sbatch_lines"], set())
    script_lines.extend(sbatch_lines)
    script_lines.append(f"#SBATCH -D {work_dir}")
    script_lines.append(f"#SBATCH --output={work_dir}/{job_name}_%j.out")
    script_lines.append(f"#SBATCH --error={work_dir}/{job_name}_%j.err")
    script_lines.append("")
    script_lines.extend(SLURM_CONFIG["env_lines"])
    script_lines.append("")

    equil_dir = Path(rst_out).parent
    script_lines.append(f"mkdir -p {equil_dir}")
    script_lines.append("")
    script_lines.append(f'echo "=== Density convergence: pmemd.cuda restart loop "')
    script_lines.append(f'echo "    target {target_density:.3f} +/- {density_tolerance:.3f} g/cc, fluctuation < {density_fluct_max:.3f}"')
    script_lines.append("")
    script_lines.append(f"RST_IN={rst_in}")
    script_lines.append(f"MAX_ITER={max_iter}")
    script_lines.append(f"TARGET={target_density}")
    script_lines.append(f"TOL={density_tolerance}")
    script_lines.append(f"FLUCT_MAX={density_fluct_max}")
    script_lines.append("iter=0")
    script_lines.append("")
    script_lines.append("# Python helper: parse time-series Density lines only (skip AVERAGES / RMS FLUCT sections).")
    script_lines.append("parse_density() {")
    script_lines.append('    python3 - "$1" "$TARGET" "$TOL" "$FLUCT_MAX" <<\'PYEOF\'')
    script_lines.append("import sys, re")
    script_lines.append("path, target, tol, fmax = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])")
    script_lines.append("try: text = open(path).read()")
    script_lines.append("except Exception: print('ERR no_mdout 0 0'); sys.exit(0)")
    script_lines.append("# Find time-series block end (start of AVERAGES section)")
    script_lines.append("avg_idx = text.find('A V E R A G E S')")
    script_lines.append("ts = text[:avg_idx] if avg_idx > 0 else text")
    script_lines.append("vals = [float(m) for m in re.findall(r'Density\\s+=\\s+([0-9.]+)', ts) if float(m) > 0.1]")
    script_lines.append("if not vals: print('ERR no_density 0 0'); sys.exit(0)")
    script_lines.append("tail = vals[-5:] if len(vals) >= 5 else vals")
    script_lines.append("mean = sum(tail)/len(tail); fluct = max(tail) - min(tail)")
    script_lines.append("ok = (abs(mean - target) <= tol) and (fluct < fmax)")
    script_lines.append("print(f\"{'YES' if ok else 'NO'} {mean:.4f} {fluct:.4f}\")")
    script_lines.append("PYEOF")
    script_lines.append("}")
    script_lines.append("")
    script_lines.append("while [ $iter -lt $MAX_ITER ]; do")
    script_lines.append(f"    OUT={equil_dir}/density_r${{iter}}.mdout")
    script_lines.append(f"    RST_OUT={equil_dir}/density_r${{iter}}.rst7")
    script_lines.append("")
    script_lines.append(f"    pmemd.cuda -O \\")
    script_lines.append(f"      -i  {burst_mdin} \\")
    script_lines.append(f"      -o  $OUT \\")
    script_lines.append(f"      -p  {prmtop} \\")
    script_lines.append(f"      -c  $RST_IN \\")
    script_lines.append(f"      -r  $RST_OUT \\")
    script_lines.append(f"      -x  /dev/null")
    script_lines.append("")
    script_lines.append("    exit_code=$?")
    script_lines.append("    read STATUS MEAN FLUCT <<< $(parse_density $OUT)")
    script_lines.append('    echo "  Iteration $iter: exit=$exit_code  mean_density=$MEAN  fluct=$FLUCT  converged=$STATUS"')
    script_lines.append("")
    script_lines.append('    if [ -f "$RST_OUT" ]; then')
    script_lines.append("        RST_IN=$RST_OUT")
    script_lines.append('        if [ $exit_code -eq 0 ] && [ "$STATUS" = "YES" ]; then')
    script_lines.append(f'            echo "  Density converged: mean=$MEAN g/cc, fluct=$FLUCT after $iter iterations"')
    script_lines.append(f'            cp $RST_OUT {rst_out}')
    script_lines.append("            break")
    script_lines.append("        elif [ $exit_code -ne 0 ]; then")
    script_lines.append('            echo "  Crashed at iter $iter, advancing from checkpoint (mean=$MEAN)..."')
    script_lines.append("        fi")
    script_lines.append("    else")
    script_lines.append('        echo "  WARNING: no rst7 at iter $iter, repeating..."')
    script_lines.append("    fi")
    script_lines.append("")
    script_lines.append("    iter=$((iter + 1))")
    script_lines.append("done")
    script_lines.append("")
    script_lines.append(f'if [ ! -f "{rst_out}" ]; then')
    script_lines.append(f'    echo "FATAL: density did not converge after $MAX_ITER iterations"')
    script_lines.append("    exit 1")
    script_lines.append("fi")

    # Optionally append production
    if prod_mdin and prod_mdout and prod_rst and prod_nc:
        prod_dir = Path(prod_mdout).parent
        script_lines.append("")
        script_lines.append(f"mkdir -p {prod_dir}")
        script_lines.append('echo "=== Production ==="')
        script_lines.append(f"pmemd.cuda -O \\")
        script_lines.append(f"  -i  {prod_mdin} \\")
        script_lines.append(f"  -o  {prod_mdout} \\")
        script_lines.append(f"  -p  {prmtop} \\")
        script_lines.append(f"  -c  {rst_out} \\")
        script_lines.append(f"  -r  {prod_rst} \\")
        script_lines.append(f'  -x  {prod_nc} || {{ echo "FATAL: prod failed"; exit 1; }}')
        script_lines.append("")
        script_lines.append('echo "=== Pipeline complete ==="')

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(script_lines) + "\n")
    logger.info(f"Wrote density-aware equil script: {output_path}")
    return {"script": str(output_path), "burst_mdin": str(burst_mdin)}


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="AmberMD Agent Toolkit — tools for AI-driven MD simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This is a TOOLKIT, not a hardcoded pipeline. The AI agent (Claude Code)
decides what to do by consulting the Amber manual via RAG, then calls
these tools to execute. Any workflow is possible.

Examples:
  python md_agent.py check-env
  python md_agent.py fetch 1UBQ
  python md_agent.py inspect 1UBQ.pdb
  python md_agent.py clean raw.pdb --output clean.pdb
  python md_agent.py rag-ingest Amber24.pdf
  python md_agent.py rag-query "umbrella sampling setup"
  python md_agent.py write-mdin min.mdin --params '{"imin":1,"maxcyc":5000,"ntb":1}'
  python md_agent.py run-amber sander -i min.mdin -o min.mdout -p sys.prmtop -c sys.inpcrd -r min.rst7
  python md_agent.py energy prod.mdout
  python md_agent.py convergence rmsd.dat
        """
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check-env", help="Report available tools and resources")

    fp = sub.add_parser("fetch", help="Download PDB from RCSB")
    fp.add_argument("pdb_id")
    fp.add_argument("--dir", default=".")

    ip = sub.add_parser("inspect", help="Analyze a PDB file")
    ip.add_argument("pdb_file")

    cp = sub.add_parser("clean", help="Clean PDB with pdb4amber")
    cp.add_argument("pdb_file")
    cp.add_argument("--output", default=None)
    cp.add_argument("--keep-waters", action="store_true")
    cp.add_argument("--keep-hydrogens", action="store_true")

    ri = sub.add_parser("rag-ingest", help="Ingest Amber manual (page-indexed)")
    ri.add_argument("manual_path")
    ri.add_argument("--output", default=None)
    ri.add_argument("--append", action="store_true", help="Append to existing index")

    rq = sub.add_parser("rag-query", help="Search manual — returns full pages")
    rq.add_argument("question")
    rq.add_argument("--top-k", type=int, default=5)

    rs = sub.add_parser("rag-section", help="Get all pages in a named section")
    rs.add_argument("section_name")

    rpg = sub.add_parser("rag-page", help="Get a specific page by number")
    rpg.add_argument("page_num", type=int)

    rpr = sub.add_parser("rag-pages", help="Get a page range (e.g., 140 150)")
    rpr.add_argument("start", type=int)
    rpr.add_argument("end", type=int)

    sub.add_parser("rag-toc", help="Show detected table of contents")

    wm = sub.add_parser("write-mdin", help="Write an Amber mdin file")
    wm.add_argument("output")
    wm.add_argument("--params", required=True, help="JSON dict of &cntrl params")
    wm.add_argument("--title", default="Generated by AmberMD Agent")
    wm.add_argument("--extra", nargs="*", help="Extra namelist sections")

    wt = sub.add_parser("write-tleap", help="Write a tLEaP input file")
    wt.add_argument("output")
    wt.add_argument("--commands", required=True)

    wc = sub.add_parser("write-cpptraj", help="Write a cpptraj input")
    wc.add_argument("output")
    wc.add_argument("--commands", required=True)

    wg = sub.add_parser("write-groupfile", help="Write a groupfile for multi-sim runs")
    wg.add_argument("output")
    wg.add_argument("--entries", required=True, help="JSON list of entry dicts")

    wf = sub.add_parser("write-file", help="Write any file")
    wf.add_argument("output")
    wf.add_argument("--content", required=True)

    ra = sub.add_parser("run-amber", help="Run an Amber MD engine")
    ra.add_argument("engine")
    ra.add_argument("-i", "--mdin", required=True)
    ra.add_argument("-o", "--mdout", required=True)
    ra.add_argument("-p", "--prmtop", required=True)
    ra.add_argument("-c", "--inpcrd", required=True)
    ra.add_argument("-r", "--rst", required=True)
    ra.add_argument("-x", "--traj", default=None)
    ra.add_argument("--ref", default=None)
    ra.add_argument("--extra", default="")

    rl = sub.add_parser("run-tleap", help="Execute tLEaP input file")
    rl.add_argument("input_file")

    rc = sub.add_parser("run-cpptraj", help="Execute cpptraj script")
    rc.add_argument("input_file")

    rp = sub.add_parser("run-program", help="Run any command")
    rp.add_argument("cmd", nargs=argparse.REMAINDER)

    # SLURM commands
    ws = sub.add_parser("write-slurm", help="Write a SLURM job script")
    ws.add_argument("output", help="Script output path")
    ws.add_argument("--commands", required=True, help="Amber commands to run")
    ws.add_argument("--job-name", default="amber_md")
    ws.add_argument("--work-dir", default=None, help="Working directory on cluster")
    ws.add_argument("--partition", default=None, help="Override partition from slurm_template.sh")
    ws.add_argument("--gpus", type=int, default=None, help="Override GPU count (0=CPU-only)")
    ws.add_argument("--walltime", default=None, help="Override walltime from slurm_template.sh (HH:MM:SS)")

    wsa = sub.add_parser("write-slurm-array", help="Write SLURM array job (umbrella/TI/REMD)")
    wsa.add_argument("output", help="Script output path")
    wsa.add_argument("--command-template", required=True, help="Command with {SLURM_ARRAY_TASK_ID} placeholder")
    wsa.add_argument("--array-range", required=True, help="e.g., 0-23 or 0-11%4")
    wsa.add_argument("--job-name", default="amber_array")
    wsa.add_argument("--work-dir", default=None)
    wsa.add_argument("--partition", default=None, help="Override partition from slurm_template.sh")
    wsa.add_argument("--gpus", type=int, default=None, help="Override GPU count (0=CPU-only)")
    wsa.add_argument("--walltime", default=None, help="Override walltime from slurm_template.sh")

    ssub = sub.add_parser("sbatch", help="Submit a SLURM job")
    ssub.add_argument("script")

    sstat = sub.add_parser("squeue", help="Check SLURM job status")
    sstat.add_argument("--job-id", type=int, default=None)

    scanc = sub.add_parser("scancel", help="Cancel a SLURM job")
    scanc.add_argument("job_id", type=int)

    shist = sub.add_parser("sacct", help="Show recent job history")
    shist.add_argument("--days", type=int, default=7)

    ep = sub.add_parser("energy", help="Parse energies from mdout")
    ep.add_argument("mdout")
    ep.add_argument("--last", type=int, default=None)

    cv = sub.add_parser("convergence", help="Check convergence of a data file")
    cv.add_argument("data_file")
    cv.add_argument("--column", type=int, default=1)
    cv.add_argument("--abs-threshold", type=float, default=0.5,
                    help="Absolute drift threshold (skill default 0.5 Å for RMSD; use 5.0 for temp K, 0.02 for density g/cc)")

    lf = sub.add_parser("ls", help="List files in a directory")
    lf.add_argument("directory", default=".", nargs="?")
    lf.add_argument("--pattern", default="*")

    rd = sub.add_parser("read", help="Read tail of a file")
    rd.add_argument("file")
    rd.add_argument("--chars", type=int, default=3000)
    rd.add_argument("--head", action="store_true")

    # --- Optimization commands ---
    pf = sub.add_parser("preflight", help="Pre-flight check a PDB before system building")
    pf.add_argument("pdb_file")
    pf.add_argument("--no-ligands", action="store_true", help="Skip ligand H-atom checks")

    lm = sub.add_parser("loop-model", help="Fill missing residue ranges using AlphaFold/ESMFold")
    lm.add_argument("--pdb", required=True, help="Crystal PDB with chain breaks")
    lm.add_argument("--missing", required=True, help="Missing ranges e.g. 'A:86-91,A:120-125'")
    lm.add_argument("--uniprot", required=True, help="UniProt accession for AlphaFold query")
    lm.add_argument("--out", required=True, help="Output assembled PDB path")

    vs = sub.add_parser("validate-step", help="Validate an MD step completed successfully (gate between pipeline steps)")
    vs.add_argument("mdout")
    vs.add_argument("--expected-nstep", type=int, default=None, help="Expected final NSTEP")
    vs.add_argument("--min-density", type=float, default=None, help="Minimum acceptable density (g/cc)")
    vs.add_argument("--max-density", type=float, default=None, help="Maximum acceptable density (g/cc)")
    vs.add_argument("--check-rst7", default=None, help="Path to rst7 file that must exist")
    vs.add_argument("--target-temp", type=float, default=300.0, help="Expected simulation temperature in K")
    vs.add_argument("--temp-tolerance", type=float, default=10.0, help="Acceptable deviation from target temp before WARN (FAIL at 2x). Default 10 K")

    vtl = sub.add_parser("validate-tleap", help="Validate a tLEaP log file")
    vtl.add_argument("log_file")

    ged = sub.add_parser("write-equil-density", help="Generate density-convergence SLURM script (pmemd.cuda restart loop)")
    ged.add_argument("output", help="SLURM script output path")
    ged.add_argument("--prmtop", required=True)
    ged.add_argument("--rst-in", required=True, help="Input rst7 (from restrained equil)")
    ged.add_argument("--rst-out", required=True, help="Output rst7 (density-converged)")
    ged.add_argument("--mdin-dir", required=True, help="Directory for burst mdin file")
    ged.add_argument("--work-dir", required=True)
    ged.add_argument("--job-name", default="equil_density")
    ged.add_argument("--prod-mdin", default=None, help="Optional: production mdin to chain")
    ged.add_argument("--prod-mdout", default=None)
    ged.add_argument("--prod-rst", default=None)
    ged.add_argument("--prod-nc", default=None)
    ged.add_argument("--max-iter", type=int, default=30)
    ged.add_argument("--target-density", type=float, default=1.00, help="Target density (g/cc). Default 1.00 — pure water at STP.")
    ged.add_argument("--density-tolerance", type=float, default=0.05, help="Tolerance around target (default 0.05 → range 0.95–1.05)")
    ged.add_argument("--density-fluct-max", type=float, default=0.02, help="Max acceptable density fluctuation in last 5 frames")
    ged.add_argument("--temperature", type=float, default=300.0, help="Simulation temperature in K")

    args = parser.parse_args()

    if args.command == "check-env":
        print(json.dumps(check_environment(), indent=2))
    elif args.command == "fetch":
        print(fetch_pdb(args.pdb_id, args.dir))
    elif args.command == "inspect":
        print(json.dumps(inspect_pdb(args.pdb_file), indent=2))
    elif args.command == "clean":
        print(clean_pdb(args.pdb_file, args.output, args.keep_waters, args.keep_hydrogens))
    elif args.command == "rag-ingest":
        print(json.dumps(rag_ingest(args.manual_path, args.output, args.append), indent=2))
    elif args.command == "rag-query":
        result = rag_query(args.question, args.top_k)
        if "error" in result:
            print(f"Error: {result['error']}\n{result.get('hint', '')}")
        else:
            for r in result["results"]:
                header = f"[Page {r['page']} | Score: {r['score']} | {r['source']}]"
                if r.get('section_path'):
                    header += f" § {r['section_path']}"
                print(f"\n{'═'*70}\n{header}\n{'─'*70}")
                text = r["text"]
                print(text[:2000] if len(text) > 2000 else text)
    elif args.command == "rag-section":
        results = rag_section(args.section_name)
        if isinstance(results, dict) and "error" in results:
            print(results["error"])
        else:
            for r in results:
                print(f"  Page {r['page']:4d} | {r['section_path']} ({r['source']})")
    elif args.command == "rag-page":
        result = rag_page(args.page_num)
        if result and "error" not in result:
            print(f"\n[Page {result['page']} | {result['source']}] § {result['section_path']}\n")
            print(result["text"])
        else:
            print(f"Page {args.page_num} not found")
    elif args.command == "rag-pages":
        results = rag_pages(args.start, args.end)
        if isinstance(results, dict) and "error" in results:
            print(results["error"])
        else:
            for r in results:
                print(f"\n{'═'*70}\n[Page {r['page']}] § {r['section_path']}\n{'─'*70}")
                print(r["text"])
    elif args.command == "rag-toc":
        result = rag_toc()
        if "error" in result:
            print(result["error"])
        else:
            print(f"\nTable of Contents ({len(result['toc'])} entries):\n")
            for entry in result["toc"]:
                print(f"  p.{entry['page']:4d}  {entry['section']}  [{entry['source']}]")
    elif args.command == "write-mdin":
        write_mdin(args.output, json.loads(args.params), args.title, args.extra)
    elif args.command == "write-tleap":
        write_tleap(args.output, args.commands.replace(";", "\n"))
    elif args.command == "write-cpptraj":
        write_cpptraj(args.output, args.commands.replace(";", "\n"))
    elif args.command == "write-groupfile":
        write_groupfile(args.output, json.loads(args.entries))
    elif args.command == "write-file":
        write_file(args.output, args.content)
    elif args.command == "run-amber":
        print(json.dumps(run_amber(args.engine, args.mdin, args.mdout, args.prmtop,
                                    args.inpcrd, args.rst, args.traj, args.ref, args.extra), indent=2))
    elif args.command == "run-tleap":
        print(json.dumps(run_tleap(args.input_file), indent=2))
    elif args.command == "run-cpptraj":
        print(json.dumps(run_cpptraj(args.input_file), indent=2))
    elif args.command == "run-program":
        print(json.dumps(run_program(" ".join(args.cmd)), indent=2))
    elif args.command == "write-slurm":
        cmds = args.commands.replace(";", "\n")
        print(write_slurm_script(args.output, cmds, job_name=args.job_name,
                                  work_dir=args.work_dir, partition=args.partition,
                                  gpus=args.gpus, walltime=args.walltime))
    elif args.command == "write-slurm-array":
        print(write_slurm_array(args.output, args.command_template,
                                 args.array_range, job_name=args.job_name,
                                 work_dir=args.work_dir, partition=args.partition,
                                 gpus=args.gpus, walltime=args.walltime))
    elif args.command == "sbatch":
        print(json.dumps(submit_slurm(args.script), indent=2))
    elif args.command == "squeue":
        print(check_slurm_job(args.job_id)["output"])
    elif args.command == "scancel":
        print(json.dumps(cancel_slurm_job(args.job_id), indent=2))
    elif args.command == "sacct":
        print(slurm_job_history(args.days)["output"])
    elif args.command == "energy":
        print(json.dumps(read_mdout(args.mdout, args.last), indent=2))
    elif args.command == "convergence":
        print(json.dumps(check_convergence(args.data_file, args.column, args.abs_threshold), indent=2))
    elif args.command == "ls":
        for f in list_files(args.directory, args.pattern):
            print(f"  {f['name']:40s} {f['size']/1024:>10.1f} KB  {f['modified']}")
    elif args.command == "read":
        fn = read_file_head if args.head else read_file_tail
        result = fn(args.file, args.chars)
        print(result.get("content", result.get("error", "")))
    elif args.command == "preflight":
        result = preflight(args.pdb_file, check_ligands=not args.no_ligands)
        print(json.dumps(result, indent=2))
    elif args.command == "loop-model":
        import subprocess as _subprocess
        result = _subprocess.run(
            [sys.executable,
             str(BASE_DIR / "scripts" / "loop_model.py"),
             "--pdb", args.pdb,
             "--missing", args.missing,
             "--uniprot", args.uniprot,
             "--out", args.out],
            check=False
        )
        sys.exit(result.returncode)
    elif args.command == "validate-step":
        result = validate_step(args.mdout, expected_nstep=args.expected_nstep,
                                min_density=args.min_density, max_density=args.max_density,
                                check_rst7=args.check_rst7, target_temp=args.target_temp,
                                temp_tolerance=args.temp_tolerance)
        print(json.dumps(result, indent=2))
    elif args.command == "validate-tleap":
        result = validate_tleap(args.log_file)
        print(json.dumps(result, indent=2))
    elif args.command == "write-equil-density":
        result = generate_equil_density_script(
            args.output, prmtop=args.prmtop, rst_in=args.rst_in,
            rst_out=args.rst_out, mdin_path=args.mdin_dir,
            work_dir=args.work_dir, job_name=args.job_name,
            prod_mdin=args.prod_mdin, prod_mdout=args.prod_mdout,
            prod_rst=args.prod_rst, prod_nc=args.prod_nc,
            max_iter=args.max_iter, target_density=args.target_density,
            density_tolerance=args.density_tolerance,
            density_fluct_max=args.density_fluct_max,
            temperature=args.temperature)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

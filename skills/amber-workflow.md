# Skill: amber-workflow

Rigid 6-step protocol for ANY simulation or analysis request. Follow every step in order. No skipping.

## Step 1 — Check Environment
```
check_environment()
```
Know what tools are available before planning.

**check_environment() reports Amber tools as missing on login node — expected.** Tools only available inside SLURM jobs after module load.
Before submitting ANY SLURM job, confirm the module-load chain works by submitting a test job:
```
write_slurm(
  output_path="/tmp/test_modules.sh",
  commands="module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh && which tleap antechamber pmemd.cuda cpptraj",
  job_name="test_modules", work_dir="/tmp", gpus=0, walltime="00:05:00"
)
submit_slurm(script_path="/tmp/test_modules.sh")
```
If any tool is missing in the SLURM output → fix module lines in `scripts/slurm_template.sh` before any submission.

## Step 2 — RAG Query + Literature Search (MANDATORY)

### 2a. Amber manual (RAG)
Run multiple queries using `rag_query()`, `rag_toc()`, `rag_section()`, `rag_pages()` (tool signatures in CLAUDE.md). Cover: protocol setup, parameter flags, analysis procedure.
If RAG index unavailable → stop, tell user to ingest manual first.

### 2b. Literature search (Europe PMC via `mcp_servers/pubmed_server.py`)
Ground planning in published practice. Run BEFORE writing PLAN.md:

```bash
python mcp_servers/pubmed_server.py search_protocol \
  '{"system_keywords": "<system from user prompt>", "simulation_type": "<MD type>", "n": 10}'
```

Extract from results: protocol lengths used (ns), force fields chosen, key observables
measured, expected value ranges. Pick 3–5 papers most relevant to PLAN.md decisions.
Save the PMID + DOI of every paper consulted — they go into PLAN.md §"Literature precedent"
AND STUDY_REPORT.md §11 References.

If literature search returns 0 hits → broaden query (drop pH, drop ligand). If still 0 →
write `[no published precedent found]` in PLAN.md so user knows decisions are skill-default only.

### 2c. Method best-practices review (MANDATORY for non-standard simulations)

**Trigger detection.** Scan user prompt AND planned simulation type for any keyword (case-insensitive substring match):

| Category | Keywords |
|----------|----------|
| Alchemical | `TI`, `FEP`, `alchemical`, `RBFE`, `ABFE` |
| Replica exchange | `REMD`, `H-REMD`, `T-REMD`, `pH-REMD`, `Hamiltonian replica` |
| Enhanced sampling | `umbrella sampling`, `SMD`, `steered MD`, `GaMD`, `LiGaMD`, `accelerated`, `metadynamics` |
| End-point methods | `MMPBSA`, `MMGBSA` |
| Protein modifications | `mutation`, `mutant`, `residue substitution`, `hybrid residue` |
| Restraints | `custom restraint`, `NMR restraint`, `distance restraint` |
| QM | `QM/MM` |

If **NO** keyword matches → skip Step 2c, proceed to Step 3.
If **ANY** keyword matches → Step 2c MUST be completed before PLAN.md approval. Continue below.

**Step 2c.1: Method-focused literature search** (separate query from Step 2b — NO system keywords):

```bash
python mcp_servers/pubmed_server.py search_protocol \
  '{"system_keywords": "<technique> best practices softcore endpoint convergence sampling",
    "simulation_type": "<technique>", "n": 10}'
```

Where `<technique>` is the matched keyword (e.g. `thermodynamic integration`, `umbrella sampling`, `MMPBSA`).

Filters to apply to results:
- Pub year ≥ (current_year − 7)
- Citation count ≥ 5
- Sort by citation count descending → take top 5

If 0 hits → broaden query (drop "best practices", just `<technique> AMBER`).
Still 0 hits → write `[no methodology precedent found]` in PLAN.md, proceed with skill defaults.

**Step 2c.2: Extract methodology keywords from top-5 abstracts.** Read each abstract, extract technique-specific jargon. Look for:
- Algorithm/method names: `smoothstep`, `softcore`, `lambda scheduling`, `Bennett acceptance ratio`, `BAR`, `MBAR`, `WHAM`, `umbrella integration`
- Amber/CHARMM-style hints: `GTI`, `improved softcore`, `decoupling`, `endpoint`
- Convergence/sampling markers: `replica exchange`, `Hamiltonian exchange`
- Force field qualifiers: `ff14SB`, `ff19SB`, `GAFF2`

Output: deduplicated list of 5–15 keywords.

**Step 2c.3: RAG manual cross-reference.** For each extracted keyword:
```
rag_query(question="<keyword> <technique>")
```
Read top 3 manual hits. Look for explicit Amber flag names: `gti_*`, `scalpha`, `scbeta`, `ifsc`, `icfe`, `noshakemask`, `barostat`, etc.

- Manual confirms paper recommendation → strong evidence → adopt the flag in PLAN.md
- Manual mentions feature but no flag → note "feature mentioned in manual, no Amber flag exposed"
- Keyword not in manual → paper-only recommendation → use default, flag in PLAN.md caveats

**Step 2c.4: Write findings into PLAN.md.** See Step 4a (`## Method best practices` section template).

## Step 3 — Pre-flight (MANDATORY before any system build)
```
preflight(pdb_file="<raw.pdb>")
```
Fix ALL flagged issues before writing tLEaP scripts. Do not proceed on FAIL.

| Flag | Fix |
|------|-----|
| Ligand no H | skills/amber-ligand.md pipeline |
| Truncated termini | `python scripts/cap_protein.py protein_only.pdb capped.pdb` |
| Modified residues (TPO/SEP/PTR) | parmed conversion |
| Disulfides | note for tLEaP bond commands |
| Chain breaks (near binding site) | investigate before proceeding |

## Step 4 — Plan (MANDATORY GATE before Step 5)

**Hard rule: write `studies/<name>/PLAN.md` AND get explicit user approval before any `sbatch`.**
This is not "tell the user" — it's "write the file, print it, ask, wait".
Without explicit approval, Step 5 must NOT begin. Skill defaults are starting points,
not final values — surface them so the user can override.

### 4a. Write `studies/<name>/PLAN.md` using the Write tool

Required sections — all values are proposed defaults the user can override:

```markdown
# Plan — <study_name>
Date: <YYYY-MM-DD>

## System (from preflight)
- PDB: <ID>, <oligomeric state>
- Biological unit: <from REMARK 350 check>
- Chains kept: <which chains>
- Atom count (estimated): <N>
- Special features: <truncated termini / disulfides / metals / cofactors / membrane / etc.>

## Force fields
| Component | FF | Reason |
|-----------|----|--------|
| Protein | ff14SB | <reason> |
| Ligand | GAFF2/BCC | <reason> |
| Water | TIP3P | <reason> |
| Ions | Joung-Cheatham | matches water model |
(Add rows for membrane/DNA/RNA/metal/cofactor as needed.)

## Protonation states (at pH <X>)
| Residue | State | Rationale |
|---------|-------|-----------|
| <e.g. ASP25 chain A> | ASH | <reason> |
| <e.g. HIS69 both chains> | HIP | pH < pKa |
(Default: standard at pH 7. Only list non-default residues.)

## Simulation protocol
| Step | Setting | Time / cycles | Source |
|------|---------|---------------|--------|
| Min1 | restrained backbone, 10 kcal/mol·Å² | 5000 cyc | skill default |
| Min2 | full | 10000 cyc | skill default |
| Heat | NVT 0→300 K, Langevin γ=2, restrained 5 kcal/mol·Å² | 100 ps | skill default |
| Burst density | NPT, barostat=1, taup=0.5, no restraint | until mean 0.95–1.05 g/cc + fluct < 0.02 | skill default |
| Equil2 | NPT, barostat=1, taup=2.0, restrained 0.5 kcal/mol·Å² | <N> ps | <see Equil2 sizing> |
| Production | NPT, MC barostat, no restraint | <N> ns | <user / default> |

### Production length defaults (if user did not specify)
| Study type | Default | Reason |
|------------|---------|--------|
| Stability check / smoke test | 10 ns | RMSD plateau |
| Ligand bound, no FE | 50 ns | conformational sampling around pose |
| Binding/MMPBSA/ΔG | 50 ns × 3 replicates | binding free energy needs replicates |
| Flap dynamics / loop / allostery | 100–500 ns | rare-event regime |
| TI / FEP / alchemical | 5 ns × N λ | per-window |
| IDP / disordered | 500 ns – 1 µs | sampling regime |

If user said a time → use it verbatim, mark source `user`.
If user did NOT say → pick default above, mark source `DEFAULT` so user notices.

### Equil2 sizing (auto-pick)
| Condition | Equil2 |
|-----------|--------|
| Small <50k atoms, burst converged ≤2 iter | 250 ps |
| Medium 50–100k OR burst 2–5 iter | 500 ps |
| Large >100k OR burst >5 iter (long cold) | 1 ns |
| Membrane | 2 ns |
Auto-extend if validate_step() shows |temp − target| > 5 K after — no extra approval needed.

## Box
- Solvent: <model>, padding <N> Å
- Ions: Joung-Cheatham, neutralize-only (default) OR <other>

## Analysis targets
- <e.g. backbone RMSD, RMSF, flap_tip distance, active_site distance>

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable / value |
|------------------------|--------|------------|-----|------------------------|
| <Author et al. Year, PMID:..., DOI:...> | <closest match> | <ns> | <ff> | <e.g. flap_tip 5.3 Å closed> |
(3–5 most relevant papers. If 0 found → "no published precedent — defaults are skill only".)

Defaults below align with / deviate from above — note any deviations and why.

## Method best practices (from Step 2c lit + RAG — MANDATORY if non-standard sim triggered)

Triggered by: <technique> (matched keyword: <keyword>)
(If Step 2c NOT triggered, write: "Standard MD — Step 2c skipped.")

| Paper (PMID, year) | Recommendation | Amber flag | Manual page | Adopted? |
|--------------------|----------------|------------|-------------|----------|
| <Author Year, PMID> | <text from abstract> | <gti_X=Y, etc.> | <page #> | ✓ or ✗ |

### Deviations from defaults (from Step 2c findings)

| Default value | New value | Reason (paper PMID + manual page) |
|---------------|-----------|-----------------------------------|
| scalpha=0.5 | scalpha=0.2 | Lee 2020 PMID:32672455 — default under gti_lam_sch=1 (manual p.513) |

If no deviations: write "Skill defaults consistent with published best practices."

## Walltime estimates
Use system-size rule (skill):

| System size | ns/day | This study walltime |
|-------------|--------|---------------------|
| <fill row matching atom count> | | min+heat ~30 min, equil2 ~30 min, prod ~<N> hr |

## Caveats / limitations
- <e.g. "1 ns insufficient for flap opening (10–100 ns regime)">
- <e.g. "Burst loop cools system — equil2 must warm back to target">
- <known cluster bugs that may surface>

## Approval: PENDING
```

### 4b. Print the plan to the user

After writing, print the PLAN.md contents to the user (not just "I wrote it").
Then state:
> "Plan written to `studies/<name>/PLAN.md`. Reply **approve** to proceed,
> or **override <field>: <new value>** to change anything (e.g. `override prod: 50 ns`,
> `override water: OPC`, `override protonation HIS69: HID`)."

### 4c. Wait — do NOT call sbatch

Hard stop here. Step 5 must not begin until the user types something.

- On **approve** →
    1. Check: if non-standard simulation triggered Step 2c, verify `## Method best practices` section in PLAN.md is non-empty AND contains at least one paper row (or explicit `[no methodology precedent found]`).
       - If missing/empty → REJECT approval. Print: `"Step 2c required — non-standard sim detected (<matched keyword>). Run method best-practices review and update PLAN.md §Method best practices before approval."` Loop back to Step 2c.
       - If present → continue.
    2. Use Edit tool to flip last line to `## Approval: APPROVED <YYYY-MM-DD>` → proceed to Step 5.
- On **override X: Y** → Edit PLAN.md, print updated version, ask again. Repeat until approve.
- On **override method_review: skip** → user explicitly bypasses Step 2c gate (rare; e.g. false-positive trigger on basic MD). Write `Step 2c skipped by user override` in PLAN.md §Method best practices, then accept normal approve.
- On any other reply → ask user to clarify approval status.

### 4d. Once approved, run autonomously through Step 5–7

Per-sbatch approval NOT required. The plan gate is a one-time checkpoint
at the start of execution. Validation gates, auto-extends, and bug-recovery
loops inside Step 5 do not need approval.

**At the start of Step 5**, initialize `studies/<study_name>/PROCESS_REPORT.md` using the `Write` tool with this template:
```
# Process Report — <study_name>
Date: <date>

## System
- PDB: <ID>
- Protein: <name>
- Ligand: <name> (CID: <N>, charge: <N>)
- Force fields: <FF table from Step 4>
- Box: <solvent model>, <padding> Å padding

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
```

After EVERY tool run:
1. Read the log (use `Read` tool)
2. Run validation gate (see below)
3. Confirm PASS before next step
4. Append result row to PROCESS_REPORT.md Steps table

### Validation Gates

**After tLEaP:** run `validate_tleap(log_file=...)`.
FAIL → do not proceed. Fix tLEaP script and re-run.
→ append to PROCESS_REPORT.md: `| tLEaP | PASS/FAIL | - | Errors=N, prmtop size |`

**After every MD step:** run `validate_step(mdout_file=..., expected_nstep=..., ...)`.
FAIL → do not proceed to next step. Diagnose first.
→ append to PROCESS_REPORT.md: `| <step> | PASS/FAIL | <JOBID> | final E, density, NSTEP |`

**After restrained equilibration — density check:**
- Density 0.90–1.10 AND fluctuation < 0.02 g/cc → proceed to production
- Density < 0.90 OR > 1.10 OR fluctuating > 0.02 → run `write_equil_density_script(output_path, prmtop, rst_in, rst_out, mdin_path, work_dir, ...)`, then submit via SLURM
⚠ NEVER use sander for density convergence (50x slower than pmemd.cuda)
⚠ barostat=1 (Berendsen) + taup=0.5 for equil2
⚠ ntwr=500 so rst7 saved even on crash
⚠ barostat=1 for ALL equil runs — barostat=2 (MC) crashes when density far from target. Only switch to barostat=2 for production.

### Task Tracking
Use TaskCreate at start — one task per major step. Update status immediately:
```
Before running    → TaskUpdate status=in_progress
After confirmed   → TaskUpdate status=completed
SLURM submitted   → in_progress immediately
SLURM finished    → completed after output check
```
Never batch-update. Task list = real-time simulation state.

### SLURM Jobs
After every sbatch:
1. Launch background poll (every 2–5 min)
2. Read `mdinfo` 30–60s after start:
   ```bash
   cat <work_dir>/mdinfo   # NSTEP, % complete, ns/day, ETA
   ```
3. When done: check outputs, proceed without waiting for user

## Step 6 — Diagnose and Adapt
On failure:
1. Read mdout/log with `Read` tool
2. `rag_query(question="<error or symptom>")` — covers Amber MD errors AND cpptraj (pages 671–865)
3. `Read("skills/amber-bugs.md")` for known cluster issues
4. Fix and retry

**cpptraj errors specifically:** `rag_query(question="cpptraj <failing command> syntax")` — full command reference in Amber24.pdf. Do this before guessing syntax.

## Step 6b — Production Restart / Extend

If production completes and more simulation time needed, or job hit walltime mid-run:
```
# extend.mdin — same as prod.mdin but:
irest=1, ntx=5,          # read velocities from rst7
nstlim=<additional_steps>
```
```bash
pmemd.cuda -O -i extend.mdin -o extend.mdout -p system.prmtop \
  -c prod.rst7 -r extend.rst7 -x extend.nc
```
Validate: `validate_step(mdout_file="extend.mdout", expected_nstep=<N>, target_temp=300)`
Concatenate trajectories for analysis: cpptraj `trajin prod.nc; trajin extend.nc`

## Step 7 — Finalize & Write Reports

Run after production + analysis complete. Write both files.

### Standard Analysis (run before writing STUDY_REPORT)

RAG-query for exact cpptraj syntax before writing scripts. Minimum analysis every simulation:

```
# analysis.in — standard post-production script
parm system/system.prmtop
trajin simulations/prod/prod.nc

# 1. Image and strip solvent
autoimage
strip :WAT,Na+,Cl-
trajout analysis/prod_stripped.nc

# 2. Align to first frame
reference simulations/prod/prod.rst7
align @CA reference

# 3. Backbone RMSD
rmsd backbone @CA,C,N out analysis/rmsd.dat

# 4. Per-residue RMSF
atomicfluct @CA out analysis/rmsf.dat byres

# 5. Energetics
run
```
```
# cpptraj via SLURM (never on login node)
write_slurm(
  output_path="studies/<study>/analysis/run_cpptraj.sh",
  commands="cd /abs/path/studies/<study>/analysis && cpptraj -i analysis.in > cpptraj.log 2>&1",
  job_name="cpptraj_<study>", work_dir="/abs/path/studies/<study>/analysis",
  gpus=0, walltime="01:00:00"
)
submit_slurm(script_path="studies/<study>/analysis/run_cpptraj.sh")
# parse energy/density/temp from mdout (runs on login node — Python only):
read_mdout(mdout_file="simulations/prod/prod.mdout")
# check RMSD plateau convergence:
check_convergence(data_file="analysis/rmsd.dat")
```

**Convergence check:** RMSD should plateau (no drift > 0.5 Å over last 50% of trajectory). If still drifting → simulation not converged → extend or report caveat in STUDY_REPORT.

### PROCESS_REPORT.md (finalize)

Append ALL sections below to existing `studies/<study_name>/PROCESS_REPORT.md`.
Goal: a user can audit the entire run without re-reading mdouts or mdin files.

```
## Decisions Source (copied from approved PLAN.md)
| Field        | Value                | Source       |
|--------------|----------------------|--------------|
| Protein FF   | ff14SB               | skill default|
| Water        | TIP3P                | skill default|
| Production   | 1 ns                 | user prompt  |
| Equil2 time  | 500 ps               | DEFAULT      |
| Protonation  | ASH-25(A), HIP-69    | agent (pH<pKa)|
(copy every row from PLAN.md so PROCESS is self-contained)

## Software / Reproducibility
- Amber: amber/24 (`module load amber/24` + `source /opt/shared/apps/amber/24/amber.sh`)
- Cluster modules loaded: <gnu12, cuda/12.4, etc. — paste from `module list` in a job log>
- pmemd.cuda version: <from `pmemd.cuda --version`>
- GPU type: <from `nvidia-smi` on compute node>
- Random seed (ig in mdin): <-1 = auto, else value>

## Performance
| Step       | ns/day achieved | Walltime estimated | Walltime actual |
|------------|-----------------|--------------------|------------------|
| Heat (NVT) | <from mdout>    | 5 min              | <wall>           |
| Equil2     | <from mdout>    | 30 min             | <wall>           |
| Production | <from mdout>    | 30 min             | <wall>           |
(Parse "ns/day" from mdout footer. Wall from SLURM job runtime — `squeue` while running, or end-of-mdout timestamps.)

## Energy / Temperature / Density Averages
Parse `read_mdout(mdout_file="<prod.mdout>")` output, paste here:
| Property    | Mean    | Std    | Range            |
|-------------|---------|--------|------------------|
| Etot        | <X>     | <X>    | <min, max>       |
| EKin        | <X>     | <X>    | <min, max>       |
| Temperature | 290.2 K | 1.8 K  | 285–295 K        |
| Density     | 1.013   | 0.005  | 1.005–1.020 g/cc |
| Pressure    | <X>     | <X>    | <min, max>       |

## Trajectory
- File: simulations/prod/prod.nc
- Frame count: <ls -lh + ntwx from mdin → N frames>
- Frame interval: <ntwx × dt in ps>
- Size: <MB>

## Convergence Summary
| Observable          | drift_abs | threshold | status      |
|---------------------|-----------|-----------|-------------|
| Backbone RMSD       | 0.25 Å    | 0.5 Å     | converged   |
| <other observables> |           |           |             |
(One row per `check_convergence()` call run during Step 7.)

## Re-runs / Auto-fixes
List every restart, density burst, or auto-extend executed without re-asking user:
- e.g. "Equil crashed at 49 ps (density blow-up). Ran write-equil-density burst, 2 iter, converged 1.011 g/cc."
- e.g. "Equil2 finished at 287 K (>5 K cold). Auto-extended 250 ps. Final 295.2 K."
If nothing was auto-fixed → write `None`.

## File Manifest
- system/system.prmtop         — topology
- system/system.inpcrd         — initial coordinates
- simulations/min1/min1.rst7   — post-min1
- simulations/equil2/equil2.rst7 — equilibrated start for prod
- simulations/prod/prod.rst7   — final prod restart
- simulations/prod/prod.nc     — production trajectory
- simulations/prod/prod.mdout  — production log
- analysis/                    — cpptraj outputs (.dat files), plots

## Validation Summary
| Gate            | Result | Value              |
|-----------------|--------|--------------------|
| tLEaP errors    | PASS   | Errors = 0         |
| Burst density   | PASS   | mean=1.01 / fluct=0.003 / 2 iter |
| Equil2 density  | PASS   | X.XX g/cc          |
| Equil2 temp     | PASS   | within ±10 K       |
| Prod completion | PASS   | NSTEP = N reached  |
| Prod energy NaN | PASS   | none detected      |
| Convergence     | PASS   | drift_abs < 0.5 Å  |

## Bugs Encountered (if any)
Document any issue agent had to work around — cluster bugs, skill gaps, tool errors.
Helps update skills/amber-bugs.md if a new pattern surfaces.
```

### STUDY_REPORT.md (scientific findings)

Write `studies/<study_name>/STUDY_REPORT.md` using the `Write` tool.
**Lock to this structure — do not freelance new sections.** Every section is
required even if short. Quantitative claims must cite the file/line they came from.

```markdown
# Study Report — <descriptive title>
Date: <YYYY-MM-DD>

## 1. Objective
One paragraph. What biological/chemical question. Why this PDB. What you expect to learn.
Distinguish "stability check" vs "binding study" vs "rare-event sampling" — sets the bar
for interpretation later.

## 2. System
- PDB: <ID>, <oligomeric state from REMARK 350>
- Chains kept / simulation construct: <which chains, why>
- Atom count: <N>
- Box: <model>, <padding> Å, <volume>
- Ligand (if any): <name, source, charge, parametrization route>
- Special features: <metals, cofactors, modified residues, disulfides, membrane>

## 3. Protonation Rationale
Required even if all standard. State the pH, then list non-default residues with
explicit reasoning (pKa from manual / literature / electrostatic context).
| Residue | State | pKa context | Rationale |
|---------|-------|-------------|-----------|

## 4. Methods (mdin settings — quote actual values used)
| Step | Ensemble | Thermostat | Barostat | dt | cut | SHAKE | Restraints | Length |
|------|----------|------------|----------|----|----|-------|------------|--------|
| Min1 | — | — | — | — | 10 Å | — | 10 kcal/mol·Å² on solute | 5000 cyc |
| Min2 | — | — | — | — | 10 Å | — | none | 10000 cyc |
| Heat | NVT | Langevin γ=2 | — | 2 fs | 10 Å | H | 5 kcal/mol·Å² | 100 ps, 0→300 K |
| Burst | NPT | Langevin γ=1 | Berendsen taup=0.5 | 2 fs | 10 Å | H | none | 10 ps × N |
| Equil2 | NPT | Langevin γ=2 | Berendsen taup=2.0 | 2 fs | 10 Å | H | 0.5 kcal/mol·Å² | <N> ps |
| Prod | NPT | Langevin γ=2 | MC taup=5.0 | 2 fs | 10 Å | H | none | <N> ns |

## 5. Results
Quantitative — every value here cites a file path. No prose-only claims.

| Observable | Mean ± std | Range | Source |
|------------|------------|-------|--------|
| Backbone RMSD | X ± X Å | min–max | analysis/rmsd_backbone.dat |
| RMSF (overall) | X Å | max=X Å at res N | analysis/rmsf.dat |
| <study-specific, e.g. flap_tip distance> | X ± X Å | | analysis/<file>.dat |
| Density | X ± X g/cc | | prod.mdout AVERAGES |
| Temperature | X ± X K | | prod.mdout AVERAGES |
| Energy (Etot) | X ± X kcal/mol | | prod.mdout AVERAGES |

If plots generated → list paths.

## 6. Convergence Assessment
| Observable | drift_abs | threshold | status |
|------------|-----------|-----------|--------|
| Backbone RMSD | X Å | 0.5 Å | converged / not_converged |

If any "not_converged" → say what was done about it: extend, accept with caveat, etc.

## 7. Key Findings
2–4 bullets, scientific conclusions only. Each bullet cites a row from §5.
Example: "Imatinib remains in ATP-pocket (ligand RMSD 1.6 Å throughout, §5)"
NOT: "the simulation went well" or "everything looks stable".

## 8. Caveats & Limitations
Required. What this study CANNOT conclude. Be specific:
- Simulation length vs required timescale ("1 ns < flap opening 10–100 ns")
- Force field limitations relevant to this system (ff14SB on IDP, GAFF2 for halogen bonds, etc.)
- Sampling: single replicate, no enhanced sampling, no replica exchange
- Starting structure bias: crystal vs solution state, crystal contacts, missing loops
- Temperature/density anomalies if present

## 9. Comparison to Literature
**Required: actually search pubmed_server, do not cite from memory.**

For each key observable in §5, run:
```bash
python mcp_servers/pubmed_server.py compare_to_literature \
  '{"observable_keyword": "<obs>", "system_keyword": "<system>", "n": 5}'
```

Then fill:
| Our value | Published value | Source (PMID:..., DOI:...) | Agreement |
|-----------|-----------------|----------------------------|-----------|
| flap_tip 5.6 Å | 5.3 ± 0.4 Å closed state | <Author Year, PMID:..., DOI:...> | ✓ |

If no relevant paper found for an observable → "No directly comparable published value" — DO NOT fabricate a citation.

## 10. Data Files
- Trajectory: simulations/prod/prod.nc (<N> frames, <interval> ps)
- Stripped trajectory: analysis/prod_stripped.nc
- Analysis: analysis/*.dat (list each)
- Reports: PROCESS_REPORT.md (engineering log)
- Approved plan: PLAN.md

## 11. References

### Method references (canonical, agent-confident)
- ff14SB: Maier et al. 2015. PMID:26574453
- TIP3P: Jorgensen 1983. doi:10.1063/1.445869
- GAFF2 / antechamber: Wang 2004. PMID:15116359
- Joung-Cheatham ions: Joung & Cheatham 2008. PMID:18593145
- Amber manual: section/page numbers consulted (cite Step 2a queries)

### System-specific literature (from pubmed_server search)
Every entry MUST be a real PMID/DOI returned by `pubmed_server.search_literature`
or `compare_to_literature`. Use:
```bash
python mcp_servers/pubmed_server.py format_citation '<record-from-search>'
```
to format. **Never** cite from training memory — `[CHECK: training-memory]` is not
acceptable; either search and cite, or omit.
```

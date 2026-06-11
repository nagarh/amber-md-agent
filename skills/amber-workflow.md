# Skill: amber-workflow

Rigid 7-step protocol for ANY simulation or analysis request. Follow every step in order. No skipping.

> **No hardcoded defaults.** Every parameter choice — FF, water, ion model, box padding, sim length, restraint strength — must be justified per study. Tier protocol in CLAUDE.md. Banned phrases in PLAN.md: `skill default`, `standard choice`, `<FF> by default`.

## Step 1 — Check Environment

```
check_environment()
```
Know what tools are available before planning.

`check_environment()` reports Amber tools as missing on the login node — expected. Tools are only available inside SLURM jobs after `module load amber/24`. Before submitting any SLURM job, confirm the module-load chain works:
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
Multiple queries via `rag_query()`, `rag_toc()`, `rag_section()`, `rag_pages()`. Cover: protocol setup, parameter flags, analysis procedure.
If RAG index unavailable → stop, tell user to ingest manual first.

### 2b. Literature search (Europe PMC via `mcp__pubmed__*`)
Ground planning in published practice. BEFORE writing PLAN.md:

```
mcp__pubmed__search_protocol(
  system_keywords="<system from user prompt>",
  simulation_type="<MD type>",
  n=10,
)
```

Extract from results: protocol lengths used (ns), force fields chosen, key observables measured, expected value ranges. Pick 3–5 most relevant papers — save PMID + DOI for PLAN.md §"Literature precedent" AND STUDY_REPORT.md §11 References.

If literature search returns 0 hits → broaden query (drop pH, drop ligand). If still 0 → write `[no published precedent found]` in PLAN.md.

### 2c. Method best-practices review (MANDATORY for non-standard simulations)

**Trigger detection.** Scan user prompt AND planned simulation type for any keyword (case-insensitive substring match):

| Category | Keywords |
|----------|----------|
| Alchemical | `TI`, `FEP`, `alchemical`, `RBFE`, `ABFE` |
| Replica exchange | `REMD`, `H-REMD`, `T-REMD`, `pH-REMD`, `Hamiltonian replica`, `REST2`, `replica` |
| Enhanced sampling | `umbrella sampling`, `SMD`, `steered MD`, `GaMD`, `LiGaMD`, `accelerated`, `metadynamics`, `ABMD`, `NEB`, `SGLD`, `string method`, `ASM`, `adaptive` |
| End-point methods | `MMPBSA`, `MMGBSA`, `decomposition`, `per-residue` |
| Protein modifications | `mutation`, `mutant`, `residue substitution`, `hybrid residue` |
| Restraints | `custom restraint`, `NMR restraint`, `distance restraint` |
| QM | `QM/MM`, `quantum` |
| Metal ion | `metalloprotein`, `zinc finger`, `zinc enzyme`, `metal ion`, `ZAFF`, `MCPB`, `12-6-4`, `Zn2+`, `Mg2+`, `Ca2+`, `Fe`, `metal binding` |
| Membrane | `membrane`, `bilayer`, `lipid`, `POPC`, `DPPC`, `POPE`, `embedded protein` |
| Nucleic acid | `RNA`, `DNA`, `nucleic`, `aptamer`, `riboswitch`, `G-quadruplex`, `siRNA` |
| Constant pH | `cpHMD`, `constant pH`, `pKa`, `protonation`, `pH-dependent` |
| Glycan | `glycoprotein`, `glycan`, `N-linked`, `carbohydrate`, `GLYCAM`, `oligosaccharide` |
| Disordered | `IDP`, `intrinsically disordered`, `disordered`, `flexible loop`, `unstructured` |
| Small molecule | `hydration free energy`, `solvation`, `GAFF`, `ligand parametrization` |

**Keyword miss fallback (CRITICAL):** If the user describes the system in scientific/biological language without technical Amber keywords (e.g., "simulate a protein that causes disease X" or "study the binding of drug Y"), the keyword table will miss. In this case:
1. Classify the simulation type from the user's description using your understanding
2. Ask yourself: "What kind of MD method does this system most likely require?" 
3. If the answer involves ANY method more specialized than plain NPT MD → trigger Step 2c

**When in doubt, always run Step 2c.** The cost of an unnecessary RAG query is ~1 second. The cost of missing a method-specific requirement is a failed simulation.

If **NO** keyword matches AND system is plain NPT MD of a protein/DNA/RNA → skip Step 2c, proceed to Step 3.
If **NO** keyword matches AND system type is unclear → trigger Step 2c with query `rag_query("MD simulation protocol for <describe system in 5 words>")`.
If **ANY** keyword matches → complete Step 2c before PLAN.md approval:

1. **Method-focused lit search** — separate from 2b, technique-only keywords: `mcp__pubmed__search_protocol(system_keywords="<technique> best practices convergence", simulation_type="<technique>", n=10)`. Triage by relevance to target observable. Method-establishing papers (pre-2015) are gold. For top hits with PMC IDs, read Methods via `get_full_text`.
2. **Extract methodology keywords** from top-5 abstracts (algorithm names, Amber flags, convergence markers, FF qualifiers). Deduplicate to 5–15 keywords.
3. **RAG cross-reference** each keyword: `rag_query("<keyword> <technique>")`. Manual confirms → adopt flag. Not in manual → paper-only, use default + caveat.
4. **Write findings** into PLAN.md §"Method best practices" (table format per `skills/templates/PLAN.md`).

## Step 3 — Pre-flight (MANDATORY before any system build)

```
preflight(pdb_file="<raw.pdb>")
```
Fix ALL flagged issues before writing tLEaP scripts. Do not proceed on FAIL.

| Flag | Fix |
|------|-----|
| Ligand no H | `skills/amber-ligand.md` pipeline |
| Truncated termini | `mcp__amber__cap_protein(input_pdb="protein_only.pdb", output_pdb="capped.pdb")` |
| Modified residues (TPO/SEP/PTR) | parmed conversion |
| Disulfides | rename CYS→CYX + CONECT records — see `amber-protein-prep.md` §Phase 3 |
| Mid-chain break (any position) | use `loop_model` first; if no AlphaFold match → find PDB without break or cap termini |
| Modeled mid-chain gap (post-loop_model) | MANDATORY call `validate_loop_junction(pdb_file=...)`. Silent 0.33 Å junction collapse caught BACE1 (Audit_3 C-01). |
| Close contacts | minimization will fix |
| Disulfides post-cap | `cap_protein` returns `disulfide_pairs` — use CONECT-only per `amber-protein-prep.md` §Phase 3. NEVER `bond mol.X.SG` tLEaP commands (fails with leaprc.gaff2). |

## Step 4 — Plan (MANDATORY GATE before Step 5)

**Hard rule: write `studies/<name>/PLAN.md` AND get explicit user approval before any `sbatch`.**
This is "write the file, print it, ask, wait" — not "tell the user". Without explicit approval, Step 5 must NOT begin.

### 4a. Write `studies/<name>/PLAN.md` using the Write tool

Use the template at `skills/templates/PLAN.md` — copy structure, fill every cell per this study. Required sections:
- System (from preflight)
- Force fields (FF table; every row cites lit PMID + manual page)
- Protonation states (pH justified, propka3 output)
- Simulation Conditions (T, P, pH, ionic strength — surface explicit so user can override)
- Simulation Protocol (Min1, Min2, Heat, Burst density, Equil2, Production)
- Box (padding + ions, agent-decided per study)
- Analysis targets (per study objective, no defaults)
- Literature precedent (3–5 papers from Step 2b)
- Method best practices (from Step 2c if triggered)
- Walltime estimates
- Caveats / limitations
- Final line: `## Approval: PENDING`

Substitute every `<placeholder>` in the template — no `<...>` remains in the written PLAN.md.

### 4b. Print the plan to the user

After writing, print the PLAN.md contents to the user (not just "I wrote it"). Then state:
> "Plan written to `studies/<name>/PLAN.md`. Reply **approve** to proceed, or **override <field>: <new value>** to change anything (e.g. `override prod: 50 ns`, `override water: OPC`, `override protonation HIS69: HID`)."

### 4c. Wait — do NOT call sbatch

Hard stop here. Step 5 must not begin until the user types something.

- On **approve** →
    1. Check: if non-standard simulation triggered Step 2c, verify `## Method best practices` section is non-empty AND contains at least one paper row (or explicit `[no methodology precedent found]`).
       - If missing/empty → REJECT approval. Print: `"Step 2c required — non-standard sim detected (<matched keyword>). Run method best-practices review and update PLAN.md §Method best practices before approval."` Loop back to Step 2c.
       - If present → continue.
    2. Use Edit tool to flip last line to `## Approval: APPROVED <YYYY-MM-DD>` → proceed to Step 5.
- On **override X: Y** → Edit PLAN.md, print updated version, ask again. Repeat until approve.
- On **override method_review: skip** → user explicitly bypasses Step 2c gate (rare; e.g. false-positive trigger). Write `Step 2c skipped by user override` in PLAN.md, then accept normal approve.
- On any other reply → ask user to clarify approval status.

## Step 5 — Execute (autonomously through Step 7)

Per-sbatch approval NOT required. The plan gate is a one-time checkpoint at the start of execution. Validation gates, auto-extends, and bug-recovery loops inside Step 5 do not need approval.

### MANDATORY: RAG-query ALL mdin parameters before writing

Before writing any mdin file, query the manual for the specific combination of method + system type:
```
rag_query(question="<method> <system_type> recommended mdin parameters nstlim dt cutoff barostat")
```
Examples:
- `rag_query("membrane protein NPT equilibration barostat cutoff nscm recommended")` → gets membrane-specific flags
- `rag_query("GaMD ntcmd nteb ntave phase lengths system size recommended")` → gets GaMD phase lengths
- `rag_query("T-REMD temperature spacing acceptance rate recommended")` → gets T-REMD ladder
- `rag_query("umbrella sampling window spacing force constant overlap")` → gets US parameters

**Do NOT copy parameter values from skill templates as-is.** Templates show structure and required flags. Values must come from:
1. RAG query for system-type-appropriate values
2. Literature precedent from Step 2b (system size, timescale)
3. Tier protocol from PLAN.md §Force fields

Skills mark RAG-required values with `<rag: ...>` — query before substituting.

### Initialize PROCESS_REPORT.md

At the start of Step 5, write `studies/<study_name>/PROCESS_REPORT.md` using the template at `skills/templates/PROCESS_REPORT.md`. The template covers both the initial header (System + Steps table) and the final-Step-7 sections (appended after analysis).

### After prep tool runs (tLEaP, antechamber, charge_check)

1. Read the log (`read_file_head` or `Read` tool)
2. Run validation gate (see below)
3. Confirm PASS before next step
4. Append result row to PROCESS_REPORT.md Steps table

### Validation Gates

**After tLEaP:** `validate_tleap(log_file=...)`.
FAIL → do not proceed. Fix tLEaP script and re-run.
→ append: `| tLEaP | PASS/FAIL | - | Errors=N, prmtop size |`

**After all MD steps complete (post-chain):** run all `validate_step` calls in parallel:
```
validate_step(mdout_file="min1.mdout", expected_nstep=<min1 maxcyc from PLAN>, ...)
validate_step(mdout_file="min2.mdout", expected_nstep=<min2 maxcyc from PLAN>, ...)
validate_step(mdout_file="heat.mdout", expected_nstep=<heat nstlim from PLAN>, target_temp=<T from PLAN Simulation Conditions>, ...)
validate_step(mdout_file="equil.mdout", expected_nstep=<equil nstlim from PLAN>, min_density=0.90, max_density=1.10, ...)
validate_step(mdout_file="equil2.mdout", expected_nstep=<equil2 nstlim from PLAN>, min_density=0.90, max_density=1.10, ...)
validate_step(mdout_file="prod.mdout", expected_nstep=<N>, ...)
```
Use the values recorded in PLAN.md — do not copy literals from this example. `target_temp` (the production/equilibration temperature `<T>`) must be justified per study via the tier protocol, not assumed.
ANY FAIL → diagnose that step's mdout (Step 6), fix, resubmit from that step forward.
→ append one row per step to PROCESS_REPORT.md

**Density check (after equil validate_step):**
- Density 0.90–1.10 g/cc AND fluctuation < 0.02 g/cc → OK
  - The 0.90–1.10 window brackets liquid-water density (~0.997 g/cc at 298 K / 1 atm); the <0.02 g/cc fluctuation cutoff is a heuristic guardrail for a converged NPT plateau. Both are equilibration-convergence criteria — see `amber-validate.md` for the authoritative check.
- Out of range → `write_equil_density_script(...)`, resubmit equil + equil2 + prod as new dependency chain

⚠ NEVER use sander for density convergence (50x slower than pmemd.cuda)
⚠ Barostat choice (rationale, not a hardcoded value): use weak-coupling (Berendsen, barostat=1) during the density burst of equil2 — barostat=2 (MC) crashes when density is far from target. Only switch to the MC barostat (barostat=2) for production once density has equilibrated. The coupling constant (e.g. taup=0.5) is an example value — justify per study via the tier protocol / `rag_query`.
⚠ Set ntwr low enough that an rst7 is saved before a possible crash (e.g. ntwr=500 for short equil). Note the benchmark default is ntwr=50000 (CLAUDE.md, storage-conservative); for the burst-density equil step a smaller ntwr is the justified exception so a restart point survives a box-change exit — record this override in PLAN.md.
⚠ restraintmask for backbone: use `@CA,C,N` — NOT `@CA,C,N,O`. TIP3P water oxygens are named `O`; including O restrains ~7000 water atoms (see `amber-bugs.md`).

### Task Tracking

Use TaskCreate at start — one task per major step. Update status immediately (`in_progress` before running, `completed` after confirmed). Never batch-update. Task list = real-time simulation state.

### SLURM Jobs — Two-Batch Dependency Chain

Split into two batches at the equil boundary. Batch 1 ends at equil so the agent can validate density and handle pmemd.cuda box-change restarts before equil2 starts. Batch 2 submits equil2→prod only after equil is confirmed converged.

#### Batch 1: min1 → min2 → heat → equil

```bash
STUDY=/abs/path/to/study
J1=$(sbatch --parsable $STUDY/simulations/min1/run_min1.sh)
J2=$(sbatch --parsable --dependency=afterok:$J1 $STUDY/simulations/min2/run_min2.sh)
J3=$(sbatch --parsable --dependency=afterok:$J2 $STUDY/simulations/heat/run_heat.sh)
J4=$(sbatch --parsable --dependency=afterok:$J3 $STUDY/simulations/equil/run_equil.sh)
echo "Batch 1 submitted. Wait on: $J4"
```

Wait on equil:
```
wait_for_slurm_job(job_id=J4, poll_interval=60)
```

Validate min1, min2, heat, equil in parallel. Then **equil-specific check:**

```
validate_step(mdout_file="equil.mdout", expected_nstep=<equil nstlim from PLAN>, min_density=0.90, max_density=1.10, ...)
```
(The 0.90–1.10 g/cc window is the water-density convergence criterion noted above; see `amber-validate.md`.)

**Equil restart loop** (handles pmemd.cuda "box dimensions changed too much" error — GPU grid becomes invalid when density changes rapidly from starting configuration. pmemd.cuda exits 0 but NSTEP < expected):

```
if equil NSTEP < expected:
    # restart from last equil.rst7 — new grid cells, density closer to target
    submit equil again: pmemd.cuda -c equil.rst7 -r equil.rst7 ...
    wait → validate → repeat until NSTEP reached OR density within the converged window (0.90–1.10 g/cc, see Density check above)
```

Only proceed to Batch 2 when equil validate_step PASS (NSTEP reached AND density OK).

#### Batch 2: equil2 → prod

```bash
J5=$(sbatch --parsable $STUDY/simulations/equil2/run_equil2.sh)
J6=$(sbatch --parsable --dependency=afterok:$J5 $STUDY/simulations/prod/run_prod.sh)
echo "Batch 2 submitted. Wait on: $J6"
```

Wait on prod:
```
wait_for_slurm_job(job_id=J6, poll_interval=60)
```

Validate equil2 + prod in parallel.

**Agent tool calls:**
- Before (sequential): 6× submit + 6× wait + 6× validate = 18 calls
- Two-batch: 2 Bash + 2 wait + 6× validate(parallel) = 10 calls

**Crash handling:** `afterok` cancels downstream jobs if any step exits non-zero. Agent detects via FAILED state from `wait_for_slurm_job` or missing rst7 in validate_step. Fix script, resubmit from failed step with new chain.

**Why split at equil:** pmemd.cuda stops with exit 0 (not crash) when box shrinks too fast during burst density equilibration. `afterok` cannot distinguish this from success — equil2 would start on under-converged rst7. Manual validation + restart loop at this boundary is required.

## Step 6 — Diagnose and Adapt

**MANDATORY FIRST ACTION on ANY failure** — before reading the log, before guessing a fix:
```
rag_query(question="<exact error string from log>")
```
The Amber24 manual has error descriptions on pages 671–865 for MD and cpptraj. RAG hit → follow manual fix exactly. No RAG hit → then read amber-bugs.md.

On failure (in order — do NOT skip):
1. **RAG first:** `rag_query(question="<copy exact error message verbatim>")` — manual has the authoritative fix
2. Read mdout/log with `Read` tool to get full context
3. `Read("skills/amber-bugs.md")` — check if this is a known cluster/tool bug
4. If RAG + bugs.md both miss: `rag_query(question="<broader symptom description>")` — try paraphrasing
5. Fix and retry

**Why RAG before reading the log:** The error message alone often matches a manual section precisely. Reading the log first anchors you to a potentially wrong hypothesis. RAG anchors to the authoritative source.

**cpptraj errors:** `rag_query(question="cpptraj <failing command> syntax example")` — full command reference in Amber24.pdf pages 671–865. The exact argument names differ from intuition. Do this before guessing any argument name.

**mdin parameter errors:** `rag_query(question="<flag name> namelist Amber24")` — flags belong to specific namelists (&cntrl, &gb, &decomp, &qmmm, &abmd, etc.). Wrong namelist = silent ignore or FATAL.

**SLURM rst7 chain guard (BUG-003):** Every SLURM script `-c` flag MUST use the PREVIOUS step's rst7. Pattern:
```
min1: -c system.inpcrd      ← initial coordinates
min2: -c min1.rst7          ← NOT system.inpcrd
heat: -c min2.rst7          ← NOT system.inpcrd
equil: -c heat.rst7         ← NOT system.inpcrd
equil2: -c equil.rst7       ← NOT system.inpcrd  
prod: -c equil2.rst7        ← NOT system.inpcrd
```
Using system.inpcrd for any step after min1 silently restarts from the crystal structure — everything runs but equilibration is broken.

### Step 6b — Production Restart / Extend

If production completes and more simulation time needed, or job hit walltime mid-run:
```
# extend.mdin — same as prod.mdin but:
irest=1, ntx=5,          # read velocities from rst7
nstlim=<additional_steps>
```
Submit extend via SLURM with `-c prod.rst7 -r extend.rst7 -x extend.nc`. Validate: `validate_step(mdout_file="extend.mdout", expected_nstep=<N>, target_temp=<T>)`. Concatenate for analysis: cpptraj `trajin prod.nc; trajin extend.nc`.

## Step 7 — Finalize & Write Reports

Run after production + analysis complete. Write both files.

### Standard Analysis (run before writing STUDY_REPORT)

For standard cpptraj analysis script (autoimage, strip, align, RMSD, RMSF, hbond) → `rag_query("cpptraj autoimage strip rmsd rmsf atomicfluct hbond standard analysis template")`. Adapt per study observables.

Submit cpptraj via SLURM (never on login node):
```
write_slurm(
  output_path="studies/<study>/analysis/run_cpptraj.sh",
  commands="cd /abs/path/studies/<study>/analysis && cpptraj -i analysis.in > cpptraj.log 2>&1",
  job_name="cpptraj_<study>", work_dir="/abs/path/studies/<study>/analysis",
  gpus=0, walltime="01:00:00"
)
submit_slurm(script_path="studies/<study>/analysis/run_cpptraj.sh")
```
Then parse + check convergence on login node (Python only):
```
read_mdout(mdout_file="simulations/prod/prod.mdout")
check_convergence(data_file="analysis/rmsd.dat")
```

**Convergence check:** RMSD should plateau — the "no drift > 0.5 Å over the last 50% of trajectory" rule is a heuristic convergence guardrail (see `amber-validate.md` / `check_convergence` for the authoritative test). If still drifting → simulation not converged → extend or report caveat in STUDY_REPORT.

### Finalize PROCESS_REPORT.md

Append the Step-7 sections (per `skills/templates/PROCESS_REPORT.md`): Decisions Source, Software/Reproducibility, Performance, Energy/Temperature/Density Averages, Trajectory, Convergence Summary, Re-runs/Auto-fixes, File Manifest, Validation Summary, Bugs Encountered.

### Write STUDY_REPORT.md

Use the template at `skills/templates/STUDY_REPORT.md`. Required sections:
1. Objective
2. System
3. Protonation Rationale
4. Methods (mdin settings — quote ACTUAL values used)
5. Results (every value cites a file path)
6. Convergence Assessment
7. Key Findings (2–4 scientific bullets, each cites §5)
8. Caveats & Limitations
9. Comparison to Literature (real pubmed search results — no training-memory citations)
10. Data Files
11. References

Every quantitative claim must cite a file/line. No prose-only claims. Compare to literature via `mcp__pubmed__compare_to_literature(observable_keyword=..., system_keyword=..., n=5)`; format citations via `mcp__pubmed__format_citation(record=..., style="amber-report")`.

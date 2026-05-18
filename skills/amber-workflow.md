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
Triage by relevance to the OBSERVABLE you need to compute, not by year or
citation count alone. Method-establishing papers (often pre-2015) are gold —
ff99SB-ILDN (2010, PMID:20408171), Joung-Cheatham ions (2008, PMID:18593145),
OPC water (2014, PMID:24858934). Year cutoffs would drop these.

For top relevant hits with PMC IDs, use `pubmed_server.get_full_text(pmcid)`
to read Methods section (FF, water, ion model, mdin parameters) — abstracts
omit protocol detail.

If 0 hits → broaden query (drop "best practices", just `<technique> AMBER`).
Still 0 hits → write `[no methodology precedent found]` in PLAN.md, fall back
to Amber 24 manual recommendations (Tier 2 in §Force fields protocol). NEVER
fall back to hardcoded defaults — agent must always cite source (lit OR manual
OR training-knowledge note).

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

**NO HARDCODED DEFAULTS.** Agent selects per study using 3-tier protocol below.
Banned: "skill default", "standard choice", "<FF> by default", copying from
prior study without re-justifying for THIS observable + this Amber version.

### Selection protocol

**Tier 1 — Lit precedent (from Step 2b/2c, primary source):**
When triaging Step 2b/2c results, extract for each paper:
- Protein FF used (ff14SB, ff19SB, a99SB-disp, ff15ipq, CHARMM36m, etc.)
- Water model (TIP3P, TIP4P-Ew, OPC, SPC/Eb, TIP4P-D, etc.)
- Ion model (Joung-Cheatham variant by water, Li-Merz, etc.)
- Reported accuracy vs experiment for the OBSERVABLE you need (Tm, ΔG, J-couplings, NMR shifts)

If a strong precedent exists for this observable + system class → candidate FF = that FF.

**Tier 2 — Amber 24 manual recommendation (if Tier 1 empty/weak):**
```
rag_query("force field recommendation <study type>")
rag_query("which protein force field <observable>")
rag_query("water model <ff candidate> compatibility")
```
The manual gives explicit recommendations by use case (e.g. ff19SB for current
general use, ff14SB for legacy compatibility, a99SB-disp for IDP+folded mixed).
Candidate FF = manual recommendation for THIS use case.

**Tier 3 — Training knowledge (if Tiers 1+2 both empty):**
Pick from training knowledge. State explicitly in PLAN.md:
"No lit precedent. No manual recommendation. Using <X> based on training
knowledge: <one-sentence reason>." User overrides at approval gate.

**ALWAYS — Manual validation (regardless of tier):**
Every candidate must be confirmed to exist in Amber 24:
```
rag_query("leaprc.protein.<name>")        # FF available
rag_query("leaprc.water.<name>")          # water available
rag_query("ions <water model> Joung-Cheatham OR Li-Merz")   # ion-water compat
```
Reject hallucinated FFs (e.g. "ff20SB" — not real) or incompatible pairings
(e.g. ff14SB-tuned ion params with OPC water without re-checking).

### PLAN.md FF table (REQUIRED format)

Every row cites BOTH lit precedent AND manual page. No row without both.

| Component | Choice | Lit precedent (PMID) | Manual page | Reason for this study |
|-----------|--------|---------------------|-------------|------------------------|
| Protein   | <name> | <PMID or "Tier 2/3: <reason>"> | Amber24 §X p.Y | <one sentence> |
| Water     | <name> | <PMID> | Amber24 §X p.Y | <one sentence> |
| Ions      | <scheme> | <PMID> | Amber24 §X p.Y | <one sentence> |
| Ligand    | <name> | <PMID or skill: amber-ligand.md> | Amber24 §X p.Y | <one sentence> |
(Add rows for membrane/DNA/RNA/metal/cofactor as needed.)

### Comparison-series studies
If this study compares to a prior study (same system, different mutation/ligand),
FF must MATCH the prior study's FF (FF effects cancel only in matched series).
Cite the prior study and re-validate FF against current manual.

## Protonation states
- pH chosen for this study: <X> (justify: biological compartment / experimental
  condition / lit precedent — NO default)
- propka3 run on starting structure: yes/no, log path

| Residue | State | Rationale |
|---------|-------|-----------|
| <residue ID> | <state code: ASH/GLH/HID/HIE/HIP/LYN/CYM> | <propka3 pKa + electrostatic context + buried/exposed status> |

Agent justifies pH choice itself in the section header — do not assume pH 7.
pH 7 (cytoplasmic) is one option; pH 5 (endosomal/lysosomal), pH 4 (gastric),
pH 8 (blood plasma in some studies) all valid per biological context.
Cite literature + propka3 calculation supporting BOTH the pH choice AND each
non-standard residue protonation state.

## Simulation Conditions (REQUIRED — surface explicitly so user can override)

| Condition | Value | Reason / source |
|-----------|-------|-----------------|
| Production temperature | <T> K | <biological context + lit PMID + manual page — NOT default 300 K> |
| Pressure | <P> atm | <NPT 1 atm standard for solution; 0 atm for vacuum; high-P studies override> |
| pH (links to §Protonation) | <X> | <see §Protonation rationale> |
| Ionic strength | <neutralize-only OR ~150 mM NaCl> | <see §Box ions> |

Surface these top-level so the user sees them in the approval gate and can override
(e.g. "actually use 310 K for fever conditions" or "use 277 K for low-T study").

Possible temperatures (NOT defaults — agent picks + justifies):
- 277 K  (4 °C, cold storage / cryo-preservation)
- 290 K  (17 °C, room-temp X-ray crystallography)
- 298 K  (25 °C, NMR standard)
- 300 K  (27 °C, common MD simulation T)
- 310 K  (37 °C, human physiological)
- 313 K  (40 °C, fever / mild heat-shock)
- 323 K  (50 °C, thermophile organisms)
- 270–600 K range  (T-REMD ladder for folding/unfolding thermodynamics)

If user prompt is silent on T, agent picks based on:
1. What temperature is the system biologically active at? (e.g. human protein → 310 K, thermophile → 333+ K)
2. What temperature was the experimental reference structure obtained at? (NMR ~298, X-ray ~290)
3. What temperature was the precedent paper run at? (Step 2b extraction)
Always cite the choice in PLAN.md and PROCESS_REPORT.md.

## Simulation Protocol

NO HARDCODED DEFAULTS. Agent fills every cell per study from:
1. Amber 24 manual (RAG-cite section + page for each parameter)
2. Lit precedent for THIS observable + system class (Step 2b PMID)
3. Training knowledge with explicit "Tier 3" note if neither has guidance

Examples of when agent MUST override conventional values:
- Kinetics studies → lower γ_ln (e.g. 0.5 instead of 2.0) to preserve dynamics
- Membrane systems → longer heating + Equil2, lipid21 thermostat handling
- IDP → longer prod + larger box than folded protein
- Free energy → matched timestep to softcore requirements (dt=0.001, ntc=1)
- Cold/high-T studies → water model + thermostat appropriate for T range

| Step | Setting | Time / cycles | Manual / lit source |
|------|---------|---------------|---------------------|
| Min1 | restrained backbone <K> kcal/mol·Å² | <N> cyc | <Amber24 §X p.Y> |
| Min2 | full | <N> cyc | <Amber24 §X p.Y> |
| Heat | NVT 0→<T> K, Langevin γ=<γ>, restrained <K> kcal/mol·Å² | <ps> | <Amber24 §X p.Y> |
| Burst density | NPT, barostat=1, taup=0.5, no restraint | until mean <ρ>±<tol> g/cc + fluct < <f> | <Amber24 §X p.Y or skills/amber-bugs.md §burst> |
| Equil2 | NPT, barostat=1, taup=<τ>, restrained <K> kcal/mol·Å² | <N> ps | <Amber24 §X p.Y + Equil2 sizing reasoning below> |
| Production | NPT, MC barostat, no restraint | <N> ns | <user / lit PMID / manual + observable-timescale reasoning> |

### Production length — NO DEFAULTS TABLE

Agent picks per study from observable + lit precedent. Reasoning chain required:

1. Identify OBSERVABLE timescale from lit (Step 2b extraction):
   - What ns/µs range did precedent papers use for THIS observable?
   - Did they report convergence (RMSD plateau, ΔG ± SEM stable)?
2. Estimate system-specific timescale (folding ~µs, binding ~10-100 ns, IDP > µs)
3. Apply user constraint (compute budget, walltime cap)
4. State chosen length in PLAN.md with: lit precedent PMID + observable timescale + caveat if shorter than precedent
5. If user gave a length verbatim → use it, mark source `user prompt`

Banned: "skill default", "DEFAULT", arbitrary round numbers without justification.

### Equil2 sizing — NO DEFAULTS TABLE

Agent picks per study from system size + density convergence behavior + observable.
Reasoning chain required:

1. System size (from preflight): tiny (<15k), small (<50k), medium (<100k), large (>100k), membrane
2. Burst loop iterations needed before convergence (from prior step)
3. Density temperature recovery time (Langevin γ + system size determines)
4. Observable sensitivity to starting conformation (drug binding needs longer equil than stability check)

Write chosen Equil2 length in PLAN.md with reasoning, cite Amber24 manual section.
Auto-extend allowed if validate_step shows |T − target| > 5 K after equilibration — log
the auto-extend in PROCESS_REPORT.md.

## Box
- Solvent model: <from PLAN §Force fields>
- Padding: <N> Å — agent picks per study. Reasoning chain:
  1. Minimum image cutoff (Amber default `cut=10` Å) + buffer for conformational
     drift → at least cut + 2 Å padding for stable folded protein
  2. Larger padding (12-15 Å) for IDP (extended states), allosteric loops, drug
     ligand binding studies where pocket conformations sample large volume
  3. Membrane systems: handled by packmol-memgen / CHARMM-GUI, NOT solvateBox
- Ions: from PLAN §Force fields (water-matched, validated)
  - Neutralization scheme: agent picks per study. Options:
    - Neutralize-only (`addIons sys <ion> 0`): for free energy / binding studies
      where added salt would alter the reference state
    - Physiological salt (~150 mM NaCl via `addIons` count): for studies where
      ionic strength matters (electrostatic interactions, IDPs, membrane potential)
  State the choice + reasoning in PLAN.md, cite manual page or precedent paper.

## Analysis targets
- <observable-specific metrics from Step 2b lit + study objective, NO defaults>
- Agent picks based on what the study aims to characterize. Examples (NOT defaults):
  backbone RMSD, RMSF, secondary structure populations, distance/angle distributions,
  fraction native contacts, Rg, end-to-end distance, ΔG decomposition, etc.

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable / value |
|------------------------|--------|------------|-----|------------------------|
| <Author et al. Year, PMID:..., DOI:...> | <closest match> | <ns> | <ff> | <observed value> |
(3–5 most relevant papers. If 0 found → "no published precedent — agent decisions
based on manual + training knowledge only, flagged for user review".)

Every parameter choice in this PLAN MUST be cross-referenced to:
- A lit row above (preferred), OR
- An Amber24 manual page (RAG-cited), OR
- An explicit "Tier 3: training knowledge — <reason>" note

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
⚠ restraintmask for backbone: use `@CA,C,N` — NOT `@CA,C,N,O`. TIP3P water oxygens are named `O`; including O in the mask restrains ~7000 water atoms and inflates restraint energy by orders of magnitude. Drop the O; carbonyl oxygens are rarely needed for structural restraint.

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
| Field        | Value                | Source                                   |
|--------------|----------------------|------------------------------------------|
| Protein FF   | <name from PLAN>     | <PMID + Amber24 §X p.Y> OR Tier 2/3 note |
| Water        | <name from PLAN>     | <PMID + Amber24 §X p.Y>                  |
| Ions         | <scheme from PLAN>   | <PMID + Amber24 §X p.Y>                  |
| Production   | <length>             | user prompt OR <PMID precedent>          |
| Equil2 time  | <length>             | <reason: size + burst convergence>       |
| Protonation  | <non-default list>   | <propka / pKa + electrostatic context>   |
(copy every row from PLAN.md verbatim. NO row may say "skill default" — every
value must cite evidence: PMID, manual page, training-knowledge rationale, OR
user prompt. PROCESS_REPORT is the auditable record.)

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

## 4. Methods (mdin settings — quote ACTUAL values used in this study)
This table is filled with the actual values from the executed mdin files —
NOT a template. Read each mdin, copy verbatim. NO hardcoded examples below.

| Step | Ensemble | Thermostat | Barostat | dt | cut | SHAKE | Restraints | Length |
|------|----------|------------|----------|----|----|-------|------------|--------|
| Min1 | — | — | — | — | <Å> | — | <K> kcal/mol·Å² <mask> | <cyc> |
| Min2 | — | — | — | — | <Å> | — | <K> kcal/mol·Å² <mask> or none | <cyc> |
| Heat | <NVT/NPT> | <type γ=X> | <type taup=X or —> | <fs> | <Å> | <H/all> | <K> kcal/mol·Å² | <ps>, <T_init>→<T_final> K |
| Burst | <NVT/NPT> | <type γ=X> | <type taup=X> | <fs> | <Å> | <H/all> | <K> kcal/mol·Å² or none | <N> × <ps> |
| Equil2 | <NVT/NPT> | <type γ=X> | <type taup=X> | <fs> | <Å> | <H/all> | <K> kcal/mol·Å² | <ps> |
| Prod | <NVT/NPT> | <type γ=X> | <type taup=X or —> | <fs> | <Å> | <H/all> | <K> kcal/mol·Å² or none | <ns> |

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

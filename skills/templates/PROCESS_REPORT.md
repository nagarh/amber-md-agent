# Template: PROCESS_REPORT.md

Created at simulation start (Step 5), updated after every validation gate, finalized after production (Step 7).
Engineering log — steps, SLURM job IDs, validation pass/fail, file manifest.
Goal: a user can audit the entire run without re-reading mdouts or mdin files.

---

## Initialize (start of Step 5)

```markdown
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
1. Read the log
2. Run validation gate (`validate_tleap` / `validate_step`)
3. Confirm PASS before next step
4. Append result row to Steps table

---

## Finalize (Step 7 — append after production + analysis)

```markdown
## Decisions Source (copied from approved PLAN.md)
| Field        | Value                | Source                                   |
|--------------|----------------------|------------------------------------------|
| Protein FF   | <name from PLAN>     | <PMID + Amber24 §X p.Y> OR Tier 2/3 note |
| Water        | <name from PLAN>     | <PMID + Amber24 §X p.Y>                  |
| Ions         | <scheme from PLAN>   | <PMID + Amber24 §X p.Y>                  |
| Production   | <length>             | user prompt OR <PMID precedent>          |
| Equil2 time  | <length>             | <reason: size + burst convergence>       |
| Protonation  | <non-default list>   | <propka / pKa + electrostatic context>   |
(copy every row from PLAN.md verbatim. NO row may say "skill default" — every value must cite evidence: PMID, manual page, training-knowledge rationale, OR user prompt.)

## Software / Reproducibility
- Amber: amber/24 (`module load amber/24` + `source /opt/shared/apps/amber/24/amber.sh`)
- Cluster modules loaded: <gnu12, cuda/12.4, etc. — paste from `module list` in a job log>
- pmemd.cuda version: <from `pmemd.cuda --version`>
- GPU type: <from `nvidia-smi` on compute node>
- Random seed (ig in mdin): <-1 = auto, else value>

## Performance
| Step       | ns/day achieved | Walltime estimated | Walltime actual |
|------------|-----------------|--------------------|------------------|
| Heat (NVT) | <from mdout>    | <est walltime>     | <wall>           |
| Equil2     | <from mdout>    | <est walltime>     | <wall>           |
| Production | <from mdout>    | <est walltime>     | <wall>           |
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
(Threshold source: 0.5 Å backbone-RMSD drift = `check_convergence()` tool default (heuristic guardrail); confirm against any Tier 1/2 precedent cited in PLAN.md before reporting "converged".)

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
<!-- ±10 K = post-equilibration acceptance window (heuristic guardrail): a run within ±10 K of the thermostat target is accepted as PASS. The tighter ">5 K cold" auto-extend trigger (see Re-runs/Auto-fixes) fires earlier and only on the cold side, so that mild under-heating is corrected by extension *before* this final gate is evaluated — the two are not in conflict: >5 K cold → auto-extend; residual deviation must still land within ±10 K to PASS. -->

| Prod completion | PASS   | NSTEP = N reached  |
| Prod energy NaN | PASS   | none detected      |
| Convergence     | PASS   | drift_abs < 0.5 Å  | <!-- 0.5 Å = check_convergence() default; see Convergence Summary note -->

## Bugs Encountered (if any)
Document any issue agent had to work around — cluster bugs, skill gaps, tool errors.
Helps update skills/amber-bugs.md if a new pattern surfaces.
```

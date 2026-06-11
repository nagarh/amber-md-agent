# Skill: amber-validate

Per-tool log validation. Read after ANY tool run before proceeding.

Use `validate_tleap(log_file=...)` and `validate_step(mdout_file=..., ...)`. For generic error strings (`Fatal Error`, `NaN`, `Could not open`, `SHAKE failure`, `abnormal termination`) — the message itself + `rag_query("<tool> <error string>")` is enough. Below covers only the non-obvious validations.

---

## tLEaP —  gotchas
- ✓ Required: `Exiting LEaP: Errors = 0`
- ✗ Stop: **Non-integer net charge** → wrong ion neutralization (silent → bad dynamics later)
- ○ Benign: `addIons: same sign` when net charge ≈ 0
- ○ Benign: terminal name formatting warnings
- **Ligand bond warnings** → ligand coords wrong → redo `amber-ligand.md` Branch C (MCS coord-transplant)

## antechamber
- ✓ Required: `Total charge of the molecule` matches expected formal charge (read via `read_file_tail`)
- Follow with parmchk2 → grep `ATTN: need revision`

## pmemd / sander — density + restraint trap
- ✓ Required: final `NSTEP = <nstlim>` reached, density ~1.0 g/cc for NPT, temperature at target
- **After restrained equil (ntr=1):** backbone restraints compete with barostat → density often ends **0.83–0.95 g/cc**. Normal — barostat cannot fully compress while restraints resist volume change.
- **Density target:** TIP3P → ~1.02 g/cc, OPC → ~0.997 g/cc. These are the published equilibrium bulk densities of the water models at 298–300 K / 1 bar: TIP3P ~1.002–1.02 g/cc (Jorgensen et al., J. Chem. Phys. 79:926, 1983; Mark & Nilsson, J. Phys. Chem. A 105:9954, 2001) and OPC ~0.997 g/cc (Izadi, Anandakrishnan & Onufriev, J. Phys. Chem. Lett. 5:3863, 2014). Confirm the model's target via `rag_query("<water model> density")`.
- **Acceptable band: 0.90–1.10 g/cc** — a wide ±~10% acceptance window around the water-model target; treated here as a heuristic guardrail for flagging a box that needs re-equilibration (no single Amber-manual citation; ~10% tolerance is a conservative engineering bound). The tighter **0.95–1.05** band in the Density Convergence loop below is the convergence *target* the remediation loop drives toward, deliberately stricter than this acceptance band so a remediated box lands comfortably inside it.
- The **0.02 g/cc fluctuation cutoff** (used in both this Decision block and the convergence loop) is a heuristic guardrail: it flags whether the box volume has stopped swinging, distinct from the mean-density band which flags the box size itself.
- **Decision:**
  - mean in 0.90–1.10 AND fluctuation < 0.02 → production OK
  - mean outside → re-equilibrate with `write_equil_density_script()`
  - fluctuation > 0.02 (large swings) → not converged, extend
  - **Never** use single-frame density. Check last 10% of equil frames.

## cpptraj
- On any error → `rag_query("cpptraj <failing command> syntax")` before guessing. Reference: Amber24.pdf §671–865.

## MMPBSA.py
- ✓ Required: `FINAL RESULTS` section present, `Errors = 0`
- ✗ Stop: ΔG values ±10000 kcal/mol (unphysical → check radii / IFBOX, see `amber-bugs.md`)

## SLURM jobs — pmemd exits 0 on GPU failure
"complete" in `.out` ≠ success. Always verify:
```bash
ls -lh <expected_output>            # file exists, non-zero size
tail -5 <mdout>                     # NSTEP reached target
grep "cudaGetDeviceCount\|Abnormal\|error" slurm_<JOBID>.out
```
For array jobs — grep EVERY task, not one representative. Nodes can have per-index GPU failures:
```bash
grep -l "cudaGetDeviceCount\|Abnormal\|error" slurm_JOBID_*.out
```

## loop_model (.meta.json + junction check) — CRITICAL
After any `loop_model(action="graft")`:

| Check | Required |
|-------|----------|
| `.meta.json` exists alongside output PDB | ✓ |
| `meta["action"] == "graft"` | ✓ |
| `meta["source"]` present + non-empty | ✓ |
| **`validate_loop_junction(pdb_file=<output_pdb>)` → `status="ok"`** | ✓ CRITICAL |

If `status="error"` → STOP. Graft produced collapsed/over-extended C-N bond (0.33 Å in BACE1). Do NOT proceed to tLEaP. Diagnose alignment (C-01/C-02 root cause) or rerun with different source.

## build_ligand_from_crystal — CRITICAL
After completion:

| Check | Required |
|-------|----------|
| `h_count_match == True` | ✓ |
| `mcs_match_pct >= 0.9` | ✓ |
| **`validate_ligand_geometry(mol2_file=<output_mol2>)` → `status="ok"`** | ✓ CRITICAL (H-04) |

If `status="error"` → H placed >2.0 Å from any heavy neighbor (36 Å outlier in BACE1). The 2.0 Å bound is a covalent-bond sanity guardrail: real X–H covalent bonds are ~0.96–1.1 Å (e.g. O–H ~0.96 Å, N–H ~1.01 Å, C–H ~1.09 Å; cf. CRC Handbook bond-length tables), so >2.0 Å is far beyond any chemical bond and signals a misplaced atom (heuristic guardrail). Do NOT proceed to antechamber. Use CCD fallback or regenerate coords.

---

## Trajectory Convergence (after production)

```
check_convergence(data_file="analysis/rmsd.dat")
```

| Result | Meaning | Action |
|--------|---------|--------|
| RMSD plateau in last 50% | Converged | Proceed to analysis + report |
| RMSD still drifting | Not converged | Extend OR note as caveat in STUDY_REPORT |
| RMSD sudden jump then plateau | Conformational transition | Note in findings — may be scientifically significant |
| RMSD > 5 Å backbone | Unstable | Check protonation, FF, minimization |

**Convergence def:** `|mean(RMSD[50%:end]) - mean(RMSD[0:50%])| < 0.5 Å`. Compare absolute values, not drift direction.

Sourcing for the three structural convergence guardrails above (all heuristic guardrails — no single canonical citation; these are widely-used MD-analysis conventions):
- **5 Å backbone-RMSD instability ceiling** — heuristic guardrail. A well-behaved folded globular protein typically equilibrates to 1–3 Å backbone RMSD from the start structure; sustained backbone RMSD > ~5 Å indicates large-scale deviation (partial unfolding, bad protonation/FF, or a poor minimization) rather than normal thermal fluctuation. Value is a conventional flag, not a hard physical limit.
- **0.5 Å inter-half RMSD tolerance** — heuristic guardrail. The mean-of-first-half vs mean-of-second-half difference is a block-averaging stationarity test; 0.5 Å is a conservative tolerance well below typical equilibrated fluctuation amplitudes, chosen to flag residual drift.
- **50% averaging-window convention** — heuristic guardrail. Splitting the trajectory at the midpoint to compare the two halves is the standard block-stationarity heuristic for detecting drift; the 50/50 split is a convention, not a derived value.

## Density Convergence (if equil outside 0.90–1.10)

Run `write_equil_density_script()`. The barostat and coupling-time choices below are tunable science parameters — justify each per study via the CLAUDE.md 4-tier protocol (Tier 1 lit precedent → Tier 2 `rag_query` manual → Tier 3 training knowledge), not as universal mandates:
- `barostat=1` (Berendsen) — rationale: Berendsen scales the box deterministically toward the target pressure, giving smooth monotonic compression that remediates a low-density box faster than the stochastic volume moves of `barostat=2` (Monte Carlo). MC is the better choice for rigorous production ensembles; for a remediation/equilibration pass aimed at recovering density quickly, Berendsen is preferred. Confirm via `rag_query("barostat Berendsen Monte Carlo pmemd")`.
- `taup=0.5` — rationale: a short pressure-relaxation time couples the box tightly to the barostat, accelerating compression during remediation. Aggressive coupling perturbs the ensemble, so it is justified only for the density-recovery pass, not production. Justify the value per study via the tier protocol; confirm via `rag_query("taup pressure relaxation time")`.
- `ntwr=500` (save rst7 even on crash) — operational guardrail, not an ensemble parameter
- Loop until density stable 0.95–1.05, fluctuation < 0.02 g/cc (see Density Convergence band below for sourcing)
- Prefer pmemd.cuda over sander for density convergence (sander ~50× slower; performance choice, not science)

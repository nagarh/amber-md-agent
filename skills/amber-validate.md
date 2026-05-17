# Skill: amber-validate

Per-tool log validation checklist. Read after ANY tool run before proceeding.

Use `validate_tleap(log_file=...)` and `validate_step(mdout_file=..., ...)` (full tool signatures in CLAUDE.md).

## Per-Tool Checklist

### tLEaP (`tleap.log` / `leap.log`)
| Status | Indicator |
|--------|-----------|
| ✓ Required | `Exiting LEaP: Errors = 0` |
| ✗ Stop | `Errors = N` (N > 0) |
| ✗ Stop | `Could not open file` |
| ✗ Stop | `Could not find atom type` |
| ✗ Stop | `Could not find bond parameter` |
| ✗ Stop | `Fatal Error` |
| ✗ Stop | Missing heavy atoms |
| ✗ Stop | Non-integer net charge (→ wrong ion neutralization) |
| ○ Benign | Terminal name formatting warnings |
| ○ Benign | `addIons: same sign` when charge ≈ 0 |

If ligand bond warnings → ligand coordinates wrong → redo skills/amber-ligand.md Branch C (MCS coord-transplant).

### antechamber (stdout / `ANTECHAMBER_*.AC`)
| Status | Indicator |
|--------|-----------|
| ✓ Required | `Total charge of the molecule` matches expected formal charge |
| ✗ Stop | `Error` |
| ✗ Stop | `cannot open` |
| ✗ Stop | `abnormal termination` |

Always follow with parmchk2. Check output for `ATTN: need revision`.

### pmemd / sander (`*.mdout`)
| Status | Indicator |
|--------|-----------|
| ✓ Required | Final `NSTEP = <nstlim>` reached |
| ✓ Required | Density ~1.0 g/cc for NPT |
| ✓ Required | Temperature stable at target |
| ✗ Stop | `FATAL ERROR` |
| ✗ Stop | `Calculation halted` |
| ✗ Stop | `NaN` in energies |
| ✗ Stop | `SHAKE failure` |

**After ANY restrained equilibration (ntr=1):** check final density. Backbone restraints compete with barostat → density often ends 0.83–0.95 g/cc after restrained equil. This is normal — barostat cannot fully compress box while backbone restraints resist volume change.

**Density target:** ~1.0 g/cc (water at STP). TIP3P equilibrates to ~1.02 g/cc; OPC to ~0.997 g/cc. Acceptable range: **0.90–1.10 g/cc**.

**Density criteria:**
- Mean density in 0.90–1.10 AND fluctuation < 0.02 g/cc → production OK
- Mean density < 0.90 OR > 1.10 → re-equilibrate with `write_equil_density_script()`
- Density fluctuating > 0.02 g/cc (large swings visible in mdout) → not converged, extend equil
- Do NOT use a single-frame density reading — check last 10% of equil frames for stability

### cpptraj (stdout)
| Status | Indicator |
|--------|-----------|
| ✓ Required | `Cpptraj: Done` |
| ✗ Stop | `Error` |
| ✗ Stop | `Could not open` |
| ✗ Stop | `no atoms selected` |

On any cpptraj error → `rag_query(question="cpptraj <failing command> syntax")` before guessing. Full reference in Amber24.pdf pages 671–865.

### MMPBSA.py (`*.dat`)
| Status | Indicator |
|--------|-----------|
| ✓ Required | `FINAL RESULTS` section present |
| ✓ Required | `Errors = 0` |
| ✗ Stop | ΔG values ±10000 kcal/mol (unphysical) |

### parmed (stdout / log)
| Status | Indicator |
|--------|-----------|
| ✓ Required | `Done!` at end |
| ✗ Stop | `Error` |
| ✗ Stop | `Could not` |
| ✗ Stop | Mask atom counts = 0 |

### SLURM jobs (`*.out` / `*.err`)

**Critical**: "complete" in `.out` ≠ success. pmemd exits 0 even on GPU failure.

Always verify:
```bash
ls -lh <expected_output>       # file exists, non-zero size
tail -5 <mdout>                # NSTEP reached target
grep "cudaGetDeviceCount\|Abnormal\|error" slurm_<JOBID>.out
```

For array jobs — check EVERY task, not one representative:
```bash
grep -l "cudaGetDeviceCount\|Abnormal\|error" slurm_JOBID_*.out
```
Nodes can have individual GPU failures affecting specific array indices only.

After confirming success:
- pmemd/sander: final NSTEP reached, no NaN, density ~1.0 g/cc
- antechamber: mol2 exists, charge matches
- tLEaP: `Errors = 0`, prmtop/inpcrd exist

## Trajectory Convergence (after production)

```
check_convergence(data_file="analysis/rmsd.dat")
```

| Result | Meaning | Action |
|--------|---------|--------|
| RMSD plateau in last 50% | Converged | Proceed to analysis and report |
| RMSD still drifting | Not converged | Extend simulation OR note as caveat in STUDY_REPORT |
| RMSD sudden jump then plateau | Conformational transition | Note in findings — may be scientifically significant |
| RMSD > 5 Å backbone | System unstable | Check protonation states, force field, minimization |

**Convergence definition:** `|mean(RMSD[50%:end]) - mean(RMSD[0:50%])| < 0.5 Å` → converged. Both halves must be compared on absolute values, not drift direction.

## Density Convergence (if equil density outside 0.90–1.10)

Run `write_equil_density_script()` (full tool signature in CLAUDE.md). Required settings:
- `barostat=1` (Berendsen) — NOT barostat=2 (MC)
- `taup=0.5`
- `ntwr=500` (save rst7 even on crash)
- Loop until density stable in 0.95–1.05 range with fluctuation < 0.02 g/cc
- Never use sander for density convergence (50x slower than pmemd.cuda)

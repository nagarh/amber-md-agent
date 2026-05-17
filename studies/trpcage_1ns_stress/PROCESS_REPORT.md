# Process Report — trpcage_1ns_stress
Date: 2026-05-17

## System
- PDB: 1L2Y
- Protein: Trp-cage miniprotein (20 residues, chain A)
- Ligand: none
- Force fields: ff14SB / TIP3P / Joung-Cheatham ions
- Box: TIP3P, 12 Å padding

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| tLEaP | PASS | 30626 | Errors=0, Warnings=2 (terminal name), 2722 WAT + 1 Cl⁻, 8471 atoms, box 52.7×50.4×43.6 Å |
| Min1 | PASS | 30627 | EAMBER=-34502 kcal/mol, restraint=4.5, rst7 199KB, 2s wall |
| Min2 | PASS | 30628 | Unrestrained, timing complete, 2s wall |
| Heat | PASS | 30629 | NSTEP=50000, T=286 K (±15 OK), Etot=243.6, rst7 398KB |
| Burst density | PASS | 30630 | 3 iter, mean=0.9974 g/cc, fluct=0.0040 (converged) |
| Equil2 | PASS | 30631 | NSTEP=125000, density=0.9962, T=290 K, rst7 398KB |
| Production | PASS | 30632 | NSTEP=500000, T_avg=300.01 K, density=0.9962, Etot=-21497 kcal/mol, 138s wall |
| cpptraj analysis | PASS | 30633 | rmsd.dat, rmsf.dat, prod_stripped.nc generated |
| Convergence | PASS | - | RMSD mean=0.77 Å, drift=0.043 Å < 0.5 threshold |

## Decisions Source (from approved PLAN.md)
| Field | Value | Source |
|-------|-------|--------|
| Protein FF | ff14SB | skill default |
| Water | TIP3P | skill default |
| Ions | Joung-Cheatham | skill default |
| Box padding | 12 Å | skill default |
| Min1 | 5000 cyc, restrained 10 kcal/mol·Å² | skill default |
| Min2 | 10000 cyc, unrestrained | skill default |
| Heat | 100 ps NVT 0→300 K, Langevin γ=2 | skill default |
| Burst | Berendsen taup=0.5, loop until 0.95–1.05 g/cc | skill default |
| Equil2 | 250 ps NPT Berendsen taup=2.0 | skill default (small system) |
| Production | 1 ns NPT MC barostat | user (study name) |
| Protonation | standard pH 7 | agent |

## Software / Reproducibility
- Amber: amber/24 (`module load amber/24` + `source /opt/shared/apps/amber/24/amber.sh`)
- Cluster modules: gnu12/12.2.0, amber/24
- Random seed: ig=-1 (auto per run)

## Performance
| Step | ns/day achieved | Walltime actual |
|------|-----------------|-----------------|
| Heat (NVT) | ~374 ns/day | ~12s |
| Equil2 | ~374 ns/day | ~60s |
| Production | 627 ns/day | 138s (2.3 min) |

## Energy / Temperature / Density Averages (from AVERAGES block, prod.mdout)
| Property | Mean | RMS Fluct |
|----------|------|-----------|
| Etot | -21497 kcal/mol | 97.1 |
| EKtot | 5096 kcal/mol | 55.2 |
| Temperature | 300.01 K | 3.25 K |
| Density | 0.9962 g/cc | — |
| VOLUME | 85425 Å³ | — |

## Trajectory
- File: simulations/prod/prod.nc
- Frame count: 500 (ntwx=1000, dt=0.002 → 1 frame per 2 ps)
- Size: ~prod.nc (check ls -lh)
- Stripped: analysis/prod_stripped.nc (1.85 MB)

## Convergence Summary
| Observable | drift_abs | threshold | status |
|------------|-----------|-----------|--------|
| Backbone RMSD | 0.043 Å | 0.5 Å | converged |

## Re-runs / Auto-fixes
Burst density required 3 iterations (iter 0: 0.845 g/cc → iter 1: 0.964 → iter 2: 0.997, converged). No restarts or auto-extends.

## File Manifest
- system/system.prmtop — topology
- system/system.inpcrd — initial coordinates
- simulations/min1/min1.rst7 — post-min1
- simulations/equil/equil2.rst7 — equilibrated start for prod
- simulations/prod/prod.rst7 — final prod restart
- simulations/prod/prod.nc — production trajectory (500 frames, 2 ps/frame)
- simulations/prod/prod.mdout — production log
- analysis/rmsd.dat — backbone RMSD time series
- analysis/rmsf.dat — per-residue RMSF
- analysis/prod_stripped.nc — solvent-stripped trajectory
- analysis/rmsd_plot.png — RMSD plot
- analysis/rmsf_plot.png — RMSF bar chart

## Validation Summary
| Gate | Result | Value |
|------|--------|-------|
| tLEaP errors | PASS | Errors=0 |
| Burst density | PASS | mean=0.997/fluct=0.004/3 iter |
| Equil2 density | PASS | 0.9962 g/cc |
| Equil2 temp | PASS | 290 K (final frame; AVERAGES=300 K) |
| Prod completion | PASS | NSTEP=500000 |
| Prod energy NaN | PASS | none detected |
| Convergence | PASS | drift_abs=0.043 Å < 0.5 Å |

## Bugs Encountered
- validate_step temp WARN (production): tool reads final-frame TEMP (290 K) not AVERAGES (300.01 K). False alarm — true average is 300.01 K per mdout AVERAGES section. Validator should read AVERAGES block, not final step.

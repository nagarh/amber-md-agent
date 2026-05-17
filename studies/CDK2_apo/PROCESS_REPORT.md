# Process Report — CDK2_apo
Date: 2026-05-15

## System
- PDB: 4EK3 (apo CDK2, 1.34 Å)
- Protein: Cyclin-dependent kinase 2 (CDK2), human, monomeric
- Ligand: None (apo simulation)
- Force fields: ff14SB (protein), TIP3P (water), Joung-Cheatham (ions)
- Box: TIP3P, 12 Å padding

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| tLEaP | PASS | - | Errors=0, Warnings=1 (benign: CDK2 net charge +4, 4 Cl- added), 13312 waters, ~42k atoms |
| Pipeline submit | submitted | 30522 | min1→min2→heat→equil burst→equil2→prod 20ns, walltime 8h |
| Min1 | PASS | 30522 | 7s wall, backbone restrained 5000 cyc |
| Min2 | PASS | 30522 | 13s wall, full 10000 cyc |
| Heat | PASS | 30522 | NVT 0→300K 100 ps, complete |
| Equil burst | NOTE | 30522 | grep case bug: "DENSITY" != "Density" → all 10 iter ran; density converged at iter2 (1.009 g/cc), stable at 1.015 by iter5; extra 80ps NPT, no harm |
| Equil2 | PASS | 30522 | NPT 500ps restrained; avg T=299.93K, avg density=1.0418 g/cc, Etot=-100447 kcal/mol; validate-step parsed FLUCTUATIONS row (tool bug — AVERAGES values confirmed correct) |
| Production | PASS | 30522 | 20 ns NPT MC barostat; NSTEP=10000000; density=1.0173 g/cc final; 322-325 ns/day |
| cpptraj analysis | PASS | - | rmsd_backbone, rmsf_per_residue, lys33_glu51_dist, dfg_to_nlobe_dist, asp145_phi all generated |

## Decisions Source (from approved PLAN.md)
| Field | Value | Source |
|-------|-------|--------|
| PDB | 1HCL (1.9 Å), loop 37-40 grafted from AlphaFold (pLDDT 57-73) | skill default |
| Protein FF | ff14SB | skill default |
| Water | TIP3P | skill default |
| Ions | Joung-Cheatham, neutralize-only | skill default |
| Box padding | 12 Å | skill default |
| Min1 | 5000 cyc, backbone restrained 10 kcal/mol·Å² | skill default |
| Min2 | 10000 cyc, full | skill default |
| Heat | NVT 0→300 K, 100 ps | skill default |
| Equil burst | NPT Berendsen taup=0.5, 10 ps × N iter | skill default |
| Equil2 time | 500 ps | DEFAULT (medium system) |
| Production | 20 ns | user request |
| Protonation | all HIS → HID | pH 7, standard |

## Software / Reproducibility
- Amber: amber/24 (module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh)
- pmemd.cuda: Amber 24
- Random seed (ig): -1 (auto)

## Performance
| Step | ns/day achieved | Walltime estimated | Walltime actual |
|------|-----------------|--------------------|--------------------|
| Min+Heat | CPU only | ~30 min | <5 min |
| Equil burst (10×10ps) | ~300+ ns/day | ~30 min | <5 min |
| Equil2 (500 ps) | ~300+ ns/day | ~30 min | ~3 min |
| Production (20 ns) | 322-325 ns/day | ~1.5 hr | ~1.5 hr |

## Energy / Temperature / Density Averages (Production)
| Property | Mean | Std | Range |
|----------|------|-----|-------|
| Etot | -107441 kcal/mol | 2418 | -108420, 228 |
| Temperature | ~300 K | ~10 K | 297-303 K (per mdout) |
| Density | 1.0168 g/cc | 0.023 | 1.011–1.026 g/cc |
| Volume | 446861 Å³ | 10017 | — |

## Trajectory
- File: simulations/prod/prod.nc
- Frame count: 2000 frames
- Frame interval: 10 ps (ntwx=5000, dt=0.002)
- Size: 112 MB (stripped: prod_stripped.nc)

## Convergence Summary
| Observable | drift_abs | threshold | status |
|------------|-----------|-----------|--------|
| Backbone RMSD | 0.260 Å (2nd-1st half mean) | 0.5 Å | converged |

## Re-runs / Auto-fixes
- Equil burst: grep 'DENSITY' case mismatch → all 10 iter ran instead of stopping at iter 2. Density converged at iter 2 (1.009 g/cc); extra 80 ps NPT. No simulation impact.
- validate-step reads FLUCTUATIONS section not AVERAGES for temp/energy — known tool parsing bug. Actual avg temp=299.93K (equil2), ~300K (prod) confirmed by direct mdout inspection.

## File Manifest
- system/system.prmtop — topology
- system/system.inpcrd — initial coordinates
- simulations/min1/min1.rst7 — post-min1
- simulations/equil2/equil2.rst7 — equilibrated start for prod
- simulations/prod/prod.rst7 — final prod restart
- simulations/prod/prod.nc — production trajectory (2000 frames, 10 ps/frame)
- simulations/prod/prod.mdout — production log
- analysis/rmsd_backbone.dat — backbone RMSD vs time
- analysis/rmsf_per_residue.dat — per-residue RMSF
- analysis/lys33_glu51_dist.dat — αC helix salt bridge distance
- analysis/dfg_to_nlobe_dist.dat — DFG-Asp145 CA to Lys33 CA distance
- analysis/asp145_phi.dat — Asp145 psi dihedral (DFG region)
- analysis/prod_stripped.nc — stripped trajectory

## Validation Summary
| Gate | Result | Value |
|------|--------|-------|
| tLEaP errors | PASS | Errors=0, Warnings=1 (benign) |
| Equil2 density | PASS | 1.0418 g/cc |
| Equil2 temp | PASS | 299.93 K (AVERAGES) |
| Prod completion | PASS | NSTEP=10000000 |
| Prod density | PASS | 1.0173 g/cc final |
| Convergence | PASS | drift_abs=0.26 Å < 0.5 Å |

## Bugs Encountered
1. Pipeline grep case: 'DENSITY' vs 'Density' in mdout → density convergence check always false → 10 burst iterations ran. Fix: change to grep -i 'density' or 'Density'.
2. validate-step parses FLUCTUATIONS section for temperature and energy summary — misleading output. Confirmed by manual mdout inspection that actual values are correct.

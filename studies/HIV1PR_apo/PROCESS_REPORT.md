# Process Report — HIV1PR_apo
Date: 2026-05-15

## System
- PDB: 1HHP (apo HIV-1 protease, BRU isolate)
- Protein: HIV-1 protease, biological dimer (chains A + B, 99 res each)
- Asymmetric unit had only chain A → applied REMARK 350 BIOMT op 2 to generate chain B
- Protonation states (pH 5.5, inhibitor-binding-relevant):
  - ASP25 chain A → ASH (mono-protonated catalytic dyad)
  - ASP25 chain B → ASP (deprotonated)
  - HIS69 both chains → HIP (pH 5.5 < pKa His ~6.0)
- Force fields: ff14SB / TIP3P / Joung-Cheatham (neutralize-only)
- Box: TIP3P, 12 Å padding, 31,296 atoms, 9386 waters

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| fetch 1HHP | PASS | - | 89 KB; correctly written to raw_pdbs/ (fetch --dir bug fix verified) |
| preflight (ASU) | FAIL → fixed | - | Bug #15 surfaced: ASU=1 chain, biological=DIMERIC. Fix → generate dimer via BIOMT |
| BIOMT dimer build | PASS | - | apply_biomt.py: 1516 atoms, chains A+B |
| set protonation | PASS | - | 28 atom lines renamed (ASH×1, HIP×2 residues) |
| tLEaP | PASS | 30516 | Errors=0, Warnings=7 (close contacts) |
| min1+min2+heat | PASS | 30517 | heat final T=284.5 K (within ±20 ramp tolerance) |
| burst density (NEW parser) | PASS | 30518 | converged iter 2: mean=1.0108, fluct=0.0033 |
| equil2 (500 ps re-equil) | PASS | 30519 | density 1.0129, temp 290.1 K (±10 K) |
| production 1 ns | PASS | 30520 | NSTEP=500000, density 1.013, temp 290.2 K |
| analysis (cpptraj) | PASS | 30521 | RMSD, RMSF, flap_tip, active_site distances |

## File Manifest
- system/1HHP_dimer_proto.pdb — biological dimer with protonation states
- system/system.prmtop — topology (5.6 MB)
- system/system.inpcrd — initial coords
- simulations/equil2/equil2.rst7 — equilibrated start for production
- simulations/prod/prod.nc — 1 ns production trajectory
- simulations/prod/prod.mdout
- analysis/rmsd_backbone.dat
- analysis/rmsf_per_residue.dat, rmsf_flaps.dat
- analysis/flap_tip_distance.dat
- analysis/active_site.dat

## Validation Summary
| Gate | Result | Value |
|------|--------|-------|
| tLEaP errors | PASS | 0 |
| burst density convergence | PASS | mean=1.0108 g/cc, fluct=0.0033 (iter 2) |
| equil2 density+temp | PASS | 1.013 g/cc, 290.1 K |
| prod completion | PASS | NSTEP=500000 (1 ns) |
| prod density | PASS | 1.013 g/cc |
| RMSD backbone convergence | PASS (skill criterion) | drift_abs=0.247 Å < 0.5 Å |
| Flap tip distance convergence | PASS | drift_abs=0.55 Å |

## New Bug Surfaced This Run
- Bug #15: preflight didn't detect REMARK 350 biological assembly mismatch → fixed post-run, verified

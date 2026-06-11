# Process Report — study_023 (Dickerson dodecamer 1BNA)
Date: 2026-06-06

## System
- PDB: 1BNA — Dickerson-Drew dodecamer d(CGCGAATTCGCG)₂, B-DNA duplex
- Ligand: none
- Force fields: DNA OL21 (`leaprc.DNA.OL21`); water OPC (`leaprc.water.opc`/OPCBOX); ions K⁺/Cl⁻ Joung–Cheatham
- Box: truncated octahedron (solvateOct), 10 Å iso padding; neutralize K⁺ + ~150 mM KCl

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| fetch 1BNA | PASS | - | raw_pdbs/1BNA.pdb, 566 atoms, chains A+B, 80 HOH |
| preflight | REVIEWED | - | only FAIL = biological_assembly false positive (BIOMT identity, duplex already complete) |
| module test | PASS | 37077 | tleap/pmemd.cuda/cpptraj/pdb4amber all present |
| pdb4amber + tLEaP pass1 | PASS | 37078 | DNA net charge −22 (22 phosphates); neutralized 22 K⁺; 5199 waters |
| tLEaP pass2 (final) | PASS | 37079 | +14 K⁺/14 Cl⁻ (~150 mM); net 0; 21,492 atoms; system.prmtop/inpcrd |
| min1 (restrained) | PASS | 37082 | NSTEP=2000, rst7 ok |
| min2 (full) | PASS | 37083 | NSTEP=5000, rst7 ok |
| heat (NVT 0→300K) | PASS | 37084 | NSTEP=50000, T=290 K, Etot ok |
| equil (NPT burst) | PASS | 37085 | NSTEP=100000, density=1.046 g/cc (AVERAGES), T=300 K. validate_step density FAIL=false-positive (read 0.0144 RMS-fluct row) |
| equil2 (NPT MC) | PASS | 37086 | NSTEP=250000, density=1.047 g/cc, T=299.9 K |
| production (50 ns) | PASS | 37087 | NSTEP=25,000,000, density=1.046 g/cc, T=299.6 K, 482 ns/day, 2.49 h wall |
| cpptraj analysis | PASS | 37098 | nastruct (BPstep/BP/Helix), RMSD core, RMSF; 5000 frames |

## Decisions Source (from approved PLAN.md)
| Field | Value | Source |
|-------|-------|--------|
| DNA FF | OL21 (`leaprc.DNA.OL21`) | user prompt; PMID 39748297, 39012172; Amber24 §3.2.2 p.40, Table 3.2 p.41 |
| Water | OPC (`leaprc.water.opc`) | PMID 39012172; Amber24 §3.6.1 p.53–54 ("improves DNA duplex") |
| Ions | K⁺/Cl⁻ Joung–Cheatham, neutralize + ~150 mM | PMID 18593145; Amber24 §13.6.5 p.249 |
| Production | 50 ns | user prompt |
| Equil2 time | 500 ps | tiny system, fast density recovery |
| Protonation | canonical (no titratable DNA bases) | n/a |

## Software / Reproducibility
- Amber 24 (`module load amber/24` + `source /opt/shared/apps/amber/24/amber.sh`); modules: gnu12/12.2.0
- Engine: pmemd.cuda, 1 GPU, node001
- Random seed: ig=-1 (auto) for all MD steps

## Performance
| Step | ns/day | Walltime actual |
|------|--------|-----------------|
| Production (50 ns) | 482 | 2.49 h (8955 s) |
| Batch 1 (min→equil) | - | ~90 s total |
| Equil2 (500 ps) | - | ~90 s |

## Energy / Temperature / Density Averages (production, final AVERAGES block)
| Property | Value |
|----------|-------|
| Temperature | 300.0 K (RMS fluct 2.3 K) |
| Density | 1.046 g/cc (RMS fluct 0.003) |
| Etot | −63060.9 kcal/mol |
| EPtot | −72950.8 kcal/mol |

## Trajectory
- File: simulations/prod/prod.nc — 1.3 GB, 5000 frames, 10 ps/frame (ntwx=5000), 50 ns

## Convergence Summary
| Observable | drift_abs | threshold | status |
|------------|-----------|-----------|--------|
| Core backbone RMSD (vs equil start, terminal bp excl.) | 0.007 Å | 0.5 Å | converged |
(check_convergence: mean 1.47 Å, std 0.29, 2nd-half mean 1.465 Å; block-averaging SEM plateaus ~0.027 Å.)

## Re-runs / Auto-fixes
None — all steps completed first attempt; equil density FAIL was a tool false-positive (confirmed real density 1.046 g/cc from AVERAGES), not a re-run.

## File Manifest
- system/system.prmtop, system/system.inpcrd, system/system.pdb
- simulations/{min1,min2,heat,equil,equil2,prod}/*.{mdin,mdout,rst7}
- simulations/prod/prod.nc — 50 ns trajectory
- analysis/{BPstep,BP,Helix}.nastruct.dat, rmsd_core.dat, rmsf.dat
- analysis/{helical_per_step,rmsd_core,rmsf}.png, analyze_helical.py

## Validation Summary
| Gate | Result | Value |
|------|--------|-------|
| tLEaP errors | PASS | Errors=0 |
| Equil density | PASS | 1.046 g/cc (AVERAGES; tool false-FAIL on RMS row) |
| Equil2 density/temp | PASS | 1.047 g/cc / 299.9 K |
| Prod completion | PASS | NSTEP=25,000,000 reached |
| Prod energy NaN | PASS | none |
| Convergence | PASS | RMSD drift 0.007 Å < 0.5 Å |

## Bugs Encountered
- validate_step density false-FAIL on equil (reads RMS-fluctuation row 0.0144 as final density) — known issue; confirmed real density via AVERAGES section. No impact.

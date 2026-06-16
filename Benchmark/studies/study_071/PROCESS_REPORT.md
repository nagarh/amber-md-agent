# Process Report — study_071: BPTI (5PTI) stability MD
Date: 2026-06-09

## System
- PDB: 5PTI (BPTI, bovine pancreatic trypsin inhibitor)
- Protein: 58-residue monomer, chain A, 3 disulfides (5-55, 14-38, 30-51)
- Ligand: none (apo — PO4/UNX/DOD HETATM stripped)
- Force fields: ff19SB protein + OPC water + Cl- (Joung-Cheatham) counter-ions
- Box: OPC truncated octahedron, 10 Å padding; net charge +6 neutralized by 6 Cl-
- Note: neutron/X-ray 1.0 Å structure — deuterium (element D) atoms stripped, tLEaP rebuilt H

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| fetch/inspect 5PTI | PASS | - | 58 res, 3 SS, 1.0 Å, neutron D atoms present |
| clean + strip HETATM/altloc | PASS | - | kept altloc A, blanked col17 |
| CYS->CYX + CONECT | PASS | - | 6 CYX, 3 CONECT pairs |
| strip deuterium (D) atoms | PASS | - | 1st charge-check exposed stray D -> stripped all D/H -> 454 heavy atoms |
| propka3 pH 7.4 | PASS | - | no overrides; all standard states |
| charge-check tLEaP | PASS | 38022 | net charge +6.000, Errors=0 -> neutralize with Cl- |
| build tLEaP (solvate+ions) | PASS | 38023 | Errors=0; 18,502 atoms; 4395 OPC waters; 6 Cl-; trunc-oct box ~59.8 Å |
| min1 (restrained) | PASS | 38024 | NSTEP=5000 |
| min2 (full) | PASS | 38025 | converged early NSTEP=4873 (grad below tol — normal); heat ran fine from it |
| heat (NVT 0->300K) | PASS | 38026 | NSTEP=50000, T=300.1 K, Etot sane |
| equil (NPT Berendsen burst) | PASS | 38027 | NSTEP=100000, density=1.018 g/cc (validate_step false-FAIL bug read RMS-fluct row 0.0145; real density confirmed from AVERAGES) |
| equil2 (NPT MC barostat) | PASS | 38028 | NSTEP=250000, density=1.019 g/cc, T=300.0 K |
| production (100 ns NPT) | PASS | 38029 | NSTEP=50,000,000 = 100 ns, density=1.0195, T=300.3 K, no NaN, 458 ns/day, 5.24 h |
| cpptraj analysis | PASS | 38039 | 2000 frames; RMSD/RMSF/Rg computed |

## Decisions Source (copied from approved PLAN.md)
| Field        | Value                | Source                                   |
|--------------|----------------------|------------------------------------------|
| Protein FF   | ff19SB               | Amber24 §3.1.1 p.33-34 (RAG); BPTI MD precedent PMID:36499117 |
| Water        | OPC                  | Amber24 §3 p.33-34, §3.6 p.52 (RAG) — ff19SB pairs best with OPC |
| Ions         | 6 Cl- (Joung-Cheatham, neutralize-only) | Amber24 §13.6.5 p.249; charge-check +6.000 |
| Production   | 100 ns               | user prompt (verbatim)                   |
| Equil2 time  | 500 ps               | tiny system (<15k atoms), fast density convergence |
| Protonation  | all standard (no overrides) | propka3 pH 7.4, all pKa far from 7.4; no HIS |

## Software / Reproducibility
- Amber: amber/24 (`module load amber/24` + `source /opt/shared/apps/amber/24/amber.sh`); module gnu12/12.2.0
- pmemd.cuda (GPU), single GPU per job (--gres=gpu:1)
- Random seed (ig in mdin): -1 (auto) for all dynamics steps
- Engine: pmemd.cuda; cpptraj for analysis

## Performance
| Step       | ns/day achieved | Walltime actual |
|------------|-----------------|------------------|
| Production | 458 ns/day      | 5.24 h (18856 s) |

## Energy / Temperature / Density Averages (prod.mdout final AVERAGES, 10000-step block)
| Property    | Mean    | Note |
|-------------|---------|------|
| Etot        | -48196.7 kcal/mol | stable |
| EPtot       | -56740.7 kcal/mol | |
| EELEC       | -66890.5 kcal/mol | well-solvated |
| Temperature | 300.01 K | target 300 K |
| Density     | 1.0195 g/cc | liquid water density OK |
| MC barostat acceptance | 29.45% | healthy |

## Trajectory
- File: simulations/prod/prod.nc
- Frame count: 2000 (ntwx=25000 steps → 50 ps/frame over 100 ns)
- Frame interval: 50 ps

## Convergence Summary
| Observable          | drift_abs | threshold | status      |
|---------------------|-----------|-----------|-------------|
| Backbone RMSD       | 0.178 Å   | 0.5 Å     | converged   |

(check_convergence: mean=1.0565 Å, first-half=1.146, second-half=0.968; block-averaging SEM stable up to block 500.)

## Re-runs / Auto-fixes
- Deuterium strip: 1st charge-check tLEaP exposed stray "D" atoms (5PTI is a neutron structure with deuterium). Stripped all element-D and -H atoms (454 heavy atoms retained), re-ran charge-check clean. No re-run of MD needed — caught at prep stage.
- No equil density-burst restart loop needed (burst converged first pass).

## File Manifest
- system/system.prmtop / system.inpcrd — topology + initial coords
- system/protein_final.pdb — cleaned, CYX, D/H-stripped protein
- simulations/{min1,min2,heat,equil,equil2,prod}/*.rst7 — restarts
- simulations/prod/prod.nc — 100 ns trajectory; prod.mdout — log
- analysis/rmsd_backbone.dat, rmsf_byres.dat, radgyr.dat, *.png

## Validation Summary
| Gate            | Result | Value              |
|-----------------|--------|--------------------|
| tLEaP errors    | PASS   | Errors = 0         |
| Burst density   | PASS   | 1.018 g/cc (from AVERAGES) |
| Equil2 density  | PASS   | 1.0192 g/cc        |
| Equil2 temp     | PASS   | 300.0 K            |
| Prod completion | PASS   | NSTEP=50,000,000 (100 ns) |
| Prod energy NaN | PASS   | none detected      |
| Convergence     | PASS   | drift_abs=0.178 Å < 0.5 Å |

## Bugs Encountered
- 5PTI is a joint X-ray/neutron structure containing deuterium (element D) atoms named D*. Standard H-count check (names starting with H or digit+H) missed them; only the charge-check tLEaP "Created a new atom named: D" warning exposed them. Fix: strip by element column (D and H) not by atom-name prefix. Worth noting in amber-protein-prep.md for neutron structures.
- validate_step density false-FAIL (known): reported 0.0145 g/cc for equil (it parsed the RMS-fluctuation row). Confirmed real density 1.018 g/cc from the AVERAGES block. Did not block the run.

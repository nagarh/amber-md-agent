# Process Report — study_087 OmpF porin in POPE/POPG bilayer
Date: 2026-06-09

## System
- PDB: 2OMF (OmpF, E. coli outer membrane porin), UniProt P02931
- Protein: OmpF trimer (chains A/B/C from BIOMT), 1011 protein residues
- Ligand: none (C8E detergent stripped)
- Force fields: ff19SB (protein) / LIPID21 (POPE:POPG 3:1) / TIP3P (water) / K+ ions
- Membrane: 427 lipids (320 POPE + 107 POPG, ratio 2.99)
- Box: ~125.9 × 125.9 × 95.5 Å, 134,333 atoms, 21,842 waters, 137 K+, net charge 0

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| fetch 2OMF | PASS | - | raw_pdbs/2OMF.pdb; 1 chain, trimeric BIOMT |
| build trimer (BIOMT) | PASS | - | system/trimer.pdb; 3 chains, C8E+water stripped |
| propka3 pH 7.0 | PASS | - | HIS21→HID, ASP127→ASH, GLU296→GLH (all 3 chains) |
| apply protonation | PASS | - | system/trimer_prot.pdb (9 overrides) |
| module test | PASS | 38491 | tleap/cpptraj/pmemd.cuda/packmol-memgen all found |
| packmol-memgen (1st) | FAIL | 38492 | aborted: 0.15 M salt < neutralizing 0.347 M (anionic PG) |
| packmol-memgen (2nd) | PASS | 38493 | saltcon 0.35 M; bilayer.pdb built (127k atoms pre-H) |
| BUG: dropped residues | FIXED | - | packmol-memgen silently dropped HID/ASH/GLH (337/chain). Fixed: feed STANDARD trimer, rename to HID/ASH/GLH AFTER packing |
| BUG: wrong box | FIXED | - | first box guess 125.9 wrong → autoimage split chains. Fixed: box 118.568/118.568/93.376 from packmol log |
| packmol-memgen rebuild | PASS | 38505 | saltcon 0.40 (neutralize anionic PG+protein); 1020 prot res, 3 HIS, 427 lipids |
| apply protonation (bilayer) | PASS | - | HID/ASH/GLH x3 chains on bilayer_prot.pdb |
| tLEaP build | PASS | 38507 | Errors=0; +6 from ASH/GLH neutralized w/ 6 Cl-; 134,408 atoms; net 0 |
| autoimage | PASS | 38508 | anchor :1-1020; 0 stretched bonds, protein intact |
| BUG: GPU heat crash | FIXED | - | 968 packmol clashes → GPU illegal-mem-access. Fixed: CPU min1/min2 (manual p.235) |
| min1 (CPU pmemd.MPI) | PASS | 38517 | 20000 cyc, restr backbone 10; E: 1.4e21 → -4.19e5 |
| min2 (CPU pmemd.MPI) | PASS | 38518 | 20000 cyc, restr backbone 2; E -4.24e5, GMAX 3.6 |
| heat (GPU) | PASS | 38551 | NVT 0→310K 200 ps; T 309.8 K |
| equil1 (GPU) | PASS | 38552 | NPT Berendsen 500 ps; density 1.038, T 310.2 K |
| equil2 (GPU) | PASS | 38566 | NPT Berendsen 1 ns, restr CA 1; density 1.048, T 310.4 K |
| equil3 (GPU) | PASS | 38567 | NPT Berendsen 2 ns, no restraint; density 1.0525, T 309.8 K |
| prod (GPU) | running | 38568 | NPT Berendsen 50 ns |

---

## Finalize (Step 7)

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| production (GPU) | PASS | 38568 | NSTEP=25,000,000 (50 ns); density 1.0545, T 310.1 K; 95.3 ns/day; 12.6 h wall |
| analysis (cpptraj) | PASS | 38794 | 1000 frames; rmsd/rmsf/eyelet/Rg/box all produced |

## Decisions Source (from approved PLAN.md)
| Field | Value | Source |
|-------|-------|--------|
| Protein FF | ff19SB | Amber24 §3 p.33; lit PMID:35294337 |
| Lipid FF | LIPID21 (POPE:POPG 3:1) | Amber24 §3.5 p.49-51; PMID:35113553 |
| Water | TIP3P | Amber24 §3.6 p.52; LIPID21-mandated (PMID:35113553) |
| Ions | K+/Cl- physiological; saltcon 0.40 (neutralize anionic PG) | Amber24 §12.9; PMID:35113553 |
| Production | 50 ns | user prompt; OmpF L3/pore 10-100 ns (PMID:39180156) |
| Protonation | HIS21→HID, ASP127→ASH, GLU296→GLH (x3 chains) | propka3 pH 7.0 |
| Barostat | Berendsen (barostat=1) throughout | Amber24 p.50 (MC deforms bilayers) |

## Software / Reproducibility
- Amber 24 (module load amber/24 + amber.sh); gnu12/12.2.0
- pmemd.cuda (GPU) for heat/equil/prod; pmemd.MPI (16 cores) for min1/min2 (packmol clash relax)
- packmol-memgen 2024.3.27; PPM3 orientation
- ig=-1 (auto random seed) for all MD
- Python: amber_development conda env (parmed, numpy, scipy)

## Performance
| Step | ns/day | Wall |
|------|--------|------|
| min1+min2 (CPU 16-core) | — | ~37 min |
| heat+equil1 (GPU) | — | ~12 min |
| equil2+equil3 (GPU) | — | ~46 min |
| production (GPU) | 95.3 | 12.6 h |

## Energy / Temperature / Density Averages (prod, last 100 records)
| Property | Mean | Note |
|----------|------|------|
| EPtot | ~-318,400 kcal/mol | stable |
| Temperature | 310.1 K | validate_step AVERAGES |
| Density | 1.0536 g/cc | range 1.052-1.056 |
| Volume | ~1.292e6 A^3 | stable |

## Trajectory
- File: simulations/prod/prod.nc (1.6 GB)
- Frames: 1000 @ 50 ps interval (ntwx=25000, dt=0.002)
- 50 ns total

## Convergence Summary
| Observable | drift_abs | threshold | status |
|------------|-----------|-----------|--------|
| Barrel backbone RMSD | 0.24 Å | 0.5 Å | converged |
| L3 loop RMSD (chain A) | 0.04 Å | 0.5 Å | converged |
| Box area | 9 A^2 (0.06%) | — | converged |

## Re-runs / Auto-fixes
- BUG-1: packmol-memgen silently dropped HID/ASH/GLH residues (337/chain instead of 340).
  Fix: fed STANDARD-named trimer to packmol, applied HID/ASH/GLH renames to bilayer.pdb AFTER packing.
- BUG-2: initial tLEaP box (125.9) wrong → autoimage split chains → 4.5 A peptide bonds.
  Fix: set box to 118.568/118.568/93.376 from packmol-memgen.log; autoimage anchor :1-1020.
- BUG-3: saltcon too low (0.15, 0.35) for anionic POPG+protein → packmol abort. Fix: 0.40 M.
- BUG-4: +6 net charge from ASH/GLH protonation → added 6 Cl- in tLEaP.
- BUG-5: GPU heat crash ("illegal memory access") from 968 packmol close contacts.
  Fix: CPU minimization (pmemd.MPI) of min1+min2 per Amber24 manual p.235 before GPU heat.

## File Manifest
- system/ompf_membrane.prmtop / .inpcrd / _centered.inpcrd — topology + coords (134,408 atoms)
- system/bilayer_prot.pdb — packed membrane with protonation states
- simulations/{min1,min2,heat,equil1,equil2,equil3,prod}/ — each step's mdin/rst7/mdout
- simulations/prod/prod.nc — 50 ns trajectory (1000 frames)
- analysis/*.dat — rmsd, rmsf, eyelet distances, Rg, box dims
- analysis/*.png — barrel RMSD, per-residue RMSF, eyelet timeseries

## Validation Summary
| Gate | Result | Value |
|------|--------|-------|
| tLEaP errors | PASS | Errors=0, net charge 0 |
| min1/min2 (CPU) | PASS | E -4.24e5, GMAX 3.6 |
| heat | PASS | T 309.8 K, NSTEP 200000 |
| equil1/2/3 density | PASS | 1.038 / 1.048 / 1.0525 g/cc |
| prod completion | PASS | NSTEP=25,000,000 reached |
| prod energy NaN | PASS | none |
| convergence | PASS | barrel drift 0.24 A < 0.5 A |

## Bugs Encountered
See Re-runs/Auto-fixes above. Notable skill-gap: amber-membrane.md should warn that
packmol-memgen silently DROPS non-standard residue names (HID/ASH/GLH) — apply protonation
renames AFTER packing, not before. Also: CPU pre-minimization (manual p.235) is REQUIRED for
clash-heavy packed membranes (GPU crashes on extreme forces) — should be the default min1 engine.

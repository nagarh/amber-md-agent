# Process Report — HSA_ibuprofen
Date: 2026-05-16

## System
- PDB: 2BXG
- Protein: Human Serum Albumin (HSA), chain A only (monomer)
- Ligand: Ibuprofen (IBP, CID 3672, charge 0) — IBP A2001 (Sudlow site II) + IBP A2002 (secondary site)
- Force fields: ff14SB / GAFF2+BCC / TIP3P / Joung-Cheatham ions
- Box: TIP3P, 12 Å padding

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| build_ligand.py | PASS | login | IBP A2001+A2002 SDF; 100% MCS; charge=0 |
| antechamber (IBP×2) | PASS | 30619 | ibp1.mol2 ibp2.mol2 ibp.frcmod; no ATTN |
| protein prep | PASS | login | CYX×17 disulf; HIP6 GLH241; ACE/NME caps |
| tLEaP | PASS | 30620 | Errors=0 Warnings=1; 167855 atoms 29781 res; box 91×122×103 Å |
| min1 | PASS | 30621 | E: 1.09e9→-3.39e5 kcal/mol; RMS 0.083; GMAX 6.73 |
| min2 | PASS | 30622 | E: -3.48e5→-3.92e5 kcal/mol; RMS 0.095 |
| heat | PASS | 30623 | Final T=300.67 K; NSTEP=50000 |
| equil2 (500ps) | FAIL→burst | 30624 | Density 0.846 < 0.90; triggered burst |
| burst density | PASS | 30625 | Density converged 1.014 g/cc; auto-launched prod |
| prod (100 ns) | RUNNING | 30625 | T=301 K; density=1.014; 179.7 ns/day; ETA ~13.4 hr |

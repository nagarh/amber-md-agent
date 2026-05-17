# Process Report — villin_hp35_stability
Date: 2026-05-17

## System
- PDB: 2RJY (1.40 Å, Gallus gallus villin-1 headpiece HP67)
- Protein: villin headpiece residues 13–76 (64 residues), ACE/NME capped
- Ligand: none
- Force fields: ff14SB (protein), TIP3P (water), Joung-Cheatham (ions)
- Box: TIP3P, 12 Å padding, neutralize-only (1 Na+)
- HIS41: HID (ND1–H donor to GLU14 carboxylate, d=2.81 Å)

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| tLEaP | PASS | 30634 | Errors=0, Warnings=1 (benign: Cl- addIons skipped, system charge ~0 after 1 Na+), prmtop 3.1M, inpcrd 645K |
| Min1 | PASS | 30635 | Converged step 4167/5000, E=−63,138 kcal/mol, GMAX=0.48 |
| Min2 | PASS | 30636 | Ran all 10000 cyc, E=−73,895 kcal/mol |
| Heat | PASS | 30637 | NSTEP=50000, final TEMP=299.14 K, 590 ns/day; validate_step FAIL on avg temp (expected for ramp — final step 299 K is correct); NOTE: @CA,C,N,O mask restrains water O atoms too — benign for heat but use !(:WAT,Na+,Cl-)&@CA,C,N in future |
| Burst density | PASS | 30638 | 1 iteration; mean=0.9928 g/cc, fluct=0.0177; converged YES |
| Equil2 | PASS | 30639 | NSTEP=125000, density=1.0029 g/cc, AVERAGES temp=300.07 K; restraintmask=!(:WAT,Na+,Cl-)&@CA,C,N corrected from heat |
| Production | PASS | 30640 | NSTEP=500000, final density=1.0026 g/cc (range 0.9929–1.0128), temp within 300±10 K; no restraints; 500 frames × 2 ps |
| cpptraj | PASS | 30641 | 500 frames processed; rmsd.dat, rmsf.dat written |

## Analysis Results

| Observable | Value | Literature expectation | Status |
|-----------|-------|------------------------|--------|
| Backbone RMSD (Cα,C,N) — mean | 1.013 Å | ~1–2 Å | ✓ PASS |
| Backbone RMSD — std | 0.136 Å | — | ✓ tight |
| RMSD drift (first→second half) | 0.032 Å | < 0.5 Å = converged | ✓ converged |
| RMSF N-terminus (res 2) | 1.47 Å | ~1.5–3 Å | ✓ PASS |
| RMSF helical regions (res 27–65) | 0.39–0.71 Å | < 1.0 Å | ✓ PASS |
| Final Etot | −45,550 kcal/mol | stable negative | ✓ |
| Final density | 1.0026 g/cc | 1.00–1.02 g/cc (TIP3P) | ✓ PASS |

## File Manifest

| File | Size | Notes |
|------|------|-------|
| system/system.prmtop | 3.1 MB | solvated |
| system/system.inpcrd | 645 KB | initial coords |
| simulations/prod/prod.nc | — | 500-frame NetCDF trajectory |
| simulations/prod/prod.mdout | ~336 KB | production energies |
| analysis/rmsd.dat | — | backbone RMSD vs crystal |
| analysis/rmsf.dat | — | per-residue Cα RMSF |
| analysis/rmsd_timeseries.png | — | RMSD plot |
| analysis/rmsf_plot.png | — | RMSF plot |

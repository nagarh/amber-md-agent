# Process Report — FKBP12_rapamycin
Date: 2026-05-14

## System
- PDB: 2DG3 (1.70 Å, clashscore 0.57)
- Protein: FKBP12 (107 residues, chain A)
- Ligand: Rapamycin RAP (CID 5284616, charge 0, C51H79NO13)
- Force fields: ff14SB / GAFF2 BCC / TIP3P / Joung-Cheatham
- Box: TIP3P octahedral, 12 Å padding
- Experimental ΔG ref: -13.57 kcal/mol (Kd 0.13 nM, ChEMBL CHEMBL5629796 2024)

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| PDB fetch (2DG3) | PASS | - | EBI PDBe 119 KB |
| PDB validation | PASS | - | 1.70 Å, clashscore 0.57, 0 outliers, 0 missing res |
| build_ligand.py (Branch C) | PASS | - | MCS 65/65 (100%), H=79, charge=0 |
| pdb4amber clean | PASS | - | GOL/HOH/altlocs stripped; RAP stripped to separate file |
| antechamber BCC | PASS | 30467 | GAFF2, 144 atoms, charge=0, no ATTN in frcmod |
| parmchk2 | PASS | 30467 | No ATTN lines |
| tLEaP | PASS | - | Errors=0, Warnings=77; 4 prmtops generated |
| min1 | PASS | 30470 | NSTEP=5000, E=-94107 kcal/mol |
| min2 | PASS | 30471 | NSTEP=5000 |
| heat | PASS | 30472 | NSTEP=10000, avg T=240.7K (ramp 0→300K normal) |
| equil (first) | FAIL | 30473 | Density burst — box dims changed too much |
| equil_density loop | PASS | 30475 | 2 iterations; density=1.008 g/cc |
| prod 50 ns | PASS | 30475 | NSTEP=25000000, T=299.7K, density=1.008, no errors |
| MM-GBSA (attempt 1) | FAIL | 30476 | gbsa=1 invalid in &gb namelist |
| MM-GBSA (attempt 2) | FAIL | 30477 | DecompError: print_res='1-107' excludes ligand residue |
| MM-GBSA (attempt 3) | PASS | 30478 | 400 frames, igb=2, idecomp=2 |
| cpptraj analysis | PASS | - | autoimage + protein-align; RMSD/RMSF computed |

## File Manifest
- system/com_solvated.prmtop    — solvated complex topology
- system/com_solvated.inpcrd    — initial coordinates
- system/com.prmtop             — dry complex (MMPBSA)
- system/rec.prmtop             — receptor only
- system/lig.prmtop             — ligand only
- simulations/prod/prod.nc      — 50 ns trajectory (5000 frames)
- simulations/prod/prod.mdout   — production log
- analysis/FINAL_RESULTS_MMPBSA.dat  — MM-GBSA summary
- analysis/FINAL_DECOMP_MMPBSA.dat   — per-residue decomp
- analysis/decomp_ranked.txt         — ranked residue contributions
- analysis/bb_rmsd.dat / lig_rmsd.dat / rmsf.dat

## Validation Summary
| Gate | Result | Value |
|------|--------|-------|
| tLEaP errors | PASS | Errors = 0 |
| equil density | PASS | 1.008 g/cc |
| prod NSTEP | PASS | 25000000 reached |
| prod energy NaN | PASS | none |
| prod temperature | PASS | 299.7 K |

# Process Report — neuraminidase_oseltamivir
Date: 2026-05-14

## System
- PDB: 6HEB (N9 neuraminidase + oseltamivir, 1.75 Å, Tern)
- Protein: Influenza A N9 neuraminidase head domain (chain A, residues 83-470, renumbered 1-389 + ACE/NME caps)
- Ligand: Oseltamivir carboxylate (G39, residue 522; CID 449381, charge 0)
- Ions: 1 structural Ca²⁺ (residue 515 original, Ca²⁺ coordinated to Asp295/Gly299/Asp326/Asn348)
- Force fields: ff14SB (protein), GAFF2/BCC (ligand), TIP3P (water), Joung-Cheatham (bulk ions)
- Box: TIP3P, 12 Å padding
- Simulation: 5 ns production

## Structure Notes
- 6HEB chosen over 2QWK (no chain breaks) and 4WA4 (missing catalytic Glu147-Asp149)
- Glycan chains B/C/D (NAG/BMA/MAN) dropped — require GLYCAM parametrization
- Ca 514 dropped — crystallographic special position (occupancy 0.20, symmetry artifact)
- Ca 515 kept — full occupancy, structurally coordinated
- Alt-loc residues handled: kept altloc A only
- 9 disulfide bonds (CYS pairs in capped numbering):
  12-338, 44-49, 96-114, 104-151, 153-158, 199-212, 201-210, 239-257, 342-368

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| antechamber G39 | PASS | 30451 | GAFF2 BCC, nc=0, mol2+frcmod written |
| tLEaP | PASS | - | Errors=0, Warnings=1, prmtop 9.2MB, 14575 WAT, 1 Na+ |
| min1 (restrained) | PASS | 30453 | 5000 steps, E=-195360 kcal/mol, RMS=0.18 |
| min2 (full) | PASS | 30454 | 5000 steps, E=-198300 kcal/mol, RMS=0.076 |
| heat (0→300K) | PASS | 30455 | 250000 steps, final T=301 K |
| equil (NPT 1ns) | PASS | 30456 | 500000 steps, T=299 K, density=1.024 g/cc |
| prod (NPT 5ns) | PASS | 30457 | 2500000 steps, T=300.0 K, density=1.0255 g/cc |
| analysis (cpptraj) | PASS | - | RMSD/RMSF/H-bonds, 1000 frames |

## File Manifest
- system/system.prmtop          — topology (9.2 MB, 49743 atoms)
- system/system.inpcrd          — initial coordinates
- system/ligand.mol2            — oseltamivir GAFF2 params (BCC charges)
- system/ligand.frcmod          — ligand frcmod
- simulations/min1,min2/        — minimization
- simulations/heat/             — 0→300 K heating
- simulations/equil/            — NPT equilibration
- simulations/prod/prod.nc      — 5 ns production trajectory (570 MB)
- simulations/prod/prod.mdout   — production log
- analysis/rmsd_backbone.dat    — backbone RMSD
- analysis/rmsd_ligand.dat      — ligand RMSD
- analysis/rmsf_ca.dat          — per-residue Cα RMSF
- analysis/hbond_ligdonor_avg.dat, hbond_ligaccep_avg.dat — oseltamivir–protein H-bonds
- analysis/plots/               — rmsd.png, rmsf.png, hbonds.png

## Validation Summary
| Gate            | Result | Value                       |
|-----------------|--------|-----------------------------|
| tLEaP errors    | PASS   | Errors = 0                  |
| min1/min2       | PASS   | RMS 0.18 / 0.076            |
| heat final temp | PASS   | 301 K                       |
| equil density   | PASS   | 1.024 g/cc                  |
| prod completion | PASS   | NSTEP = 2500000 reached     |
| prod temp       | PASS   | 300.0 ± 1.3 K               |
| prod density    | PASS   | 1.0255 ± 0.0021 g/cc        |
| prod energy NaN | PASS   | none detected               |

## Issues Encountered & Fixes
- SLURM module load: `openmpi4/4.1.5` failed — needs `gnu12/12.2.0` prereq. Fixed scripts/slurm_template.sh.
- tLEaP syntax error: multi-line comment from semicolon split. Fixed comment.
- Ca²⁺ residue name: Amber expects `CA` not `CAL`. Renamed in ca_ions.pdb.
- Disulfides: `bond` command alone insufficient — renamed all 18 disulfide CYS → CYX in PDB.

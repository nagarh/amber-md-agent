# Process Report — HSP90_radicicol
Date: Thu May 14 04:20:49 PM PDT 2026

## System
- PDB: 4EGK (HSP90-alpha N-terminal ATPase domain + radicicol, 1.69 Å)
- Protein: HSP90-alpha (chain A, ACE-capped PRO11 N-term, NME-capped LYS215 C-term)
- Ligand: Radicicol RDC (CID: 6323491, charge: 0, formula: C18H17ClO6)
- Force fields: ff14SB (protein), GAFF2/AM1-BCC (ligand), TIP3P (water), Joung-Cheatham (ions)
- Box: TIP3P, 12 Å padding, 0.15 M NaCl

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| Fetch 4EGK | PASS | - | 322947 bytes, wwPDB mirror |
| Preflight | PASS | - | Capped PRO11→ACE, LYS215→NME; alt locs handled by pdb4amber |
| Ligand prep | PASS | - | MCS 100%, H=17, charge=0, ligand_ready.sdf |
| Antechamber | IN PROGRESS | 30458 | GAFF2/BCC, nc=0 |

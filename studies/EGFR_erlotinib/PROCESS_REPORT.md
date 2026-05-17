# Process Report — EGFR_erlotinib
Date: 2026-05-14

## System
- PDB: 1IEP (Abl kinase / imatinib STI-571, chain A)
- Protein: Abl kinase domain (chain A, capped ACE/NME)
- Ligand: STI (imatinib, 37 heavy atoms + 31 H, charge=0)
- Force fields: ff14SB | GAFF2 (BCC) | TIP3P | Joung-Cheatham ions
- Box: TIP3PBOX, 12 Å padding

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| CCD ligand prep | PASS | 30434 | MCS 37/37 100%, H=31, charge=0, 0 ATTN |
| tLEaP | PASS | - | Errors=0, Warnings=1 (BCC residual), prmtop 7.8M |
| minimization | PASS | 30435 | 500 cycles, FINAL RESULTS reached, EAMBER=-162278.7 |
| heating | PASS | 30436 | NSTEP=1000, 0→300 K ramp, heat.nc 5M |

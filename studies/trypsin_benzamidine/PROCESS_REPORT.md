# Process Report — trypsin_benzamidine
Date: 2026-05-16

## System
- PDB: 3PTB, 1.7 Å, bovine β-trypsin + BEN
- Protein: chain A, residues 16–245 (chymotrypsinogen numbering, 220 AA continuous)
- Ligand: BEN (benzamidine, +1 amidinium, 9 heavy + 8 H)
- Force fields: ff14SB | GAFF2 (BCC) | TIP3P | Joung-Cheatham
- Box: TIP3PBOX, 18 Å padding (pull range = 17 Å)
- Termini: NO CAPS — Ile16/Asn245 are mature trypsin native termini (activation cleavage), skill default of capping for resnum≠1 is overridden here.

## Atom indices (post-tleap)
- BEN heavy atoms: 3222-3230 (9 atoms, for COM group in `&rst iat<0`)
- Asp189-Cα (tleap res 170): atom **2467**
- Asp194-Cα (tleap res 175): atom 2524 (reference, not used)
- Bound salt-bridge: ASP170-OD1 ↔ BEN-N1 = 2.92 Å (correct, BEN+1 binds Asp189-)
- System: 51,434 atoms; 16,062 waters; 9 Cl⁻ (BEN+1 + 6 K/R protein); Net charge = -0.001 ✓
- Box: 85.2 × 80.7 × 90.8 Å orthorhombic (room for 17 Å pull)

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| pdb4amber | PASS | 30585 | --noter; 6 CONECT (SS bonds); 0 TER |
| antechamber BEN+1 | PASS | 30585 | GAFF2-BCC, -nc 1 |
| tleap build | PASS | 30585 | Errors=0, Warnings=3 (benign); prmtop 8.7M |
| min1 + min2 | PASS | 30586 | restrained 10 kcal then unrestrained, exit 0 |
| heat NVT 100 ps | PASS | 30586 | 0->300 K, Langevin γ=2, restraint 5 |
| burst NPT × 5 | PASS | 30586 | final ρ=1.005 g/cc |
| equil2 500 ps NPT | PASS | 30586 | T=299.83 K, ρ=1.0050 g/cc |
| prepull 1 ns NPT MC | PASS | 30586 | T=300.11 K, ρ=1.0055 g/cc |
| sMD pull 28 ns | PASS | 30588 | r 3.15→17.13 Å, W_jar=10.43 kcal/mol, ns/day=295; 1400 traj frames |
| cpptraj window extract | PASS | 30589 | 29 start.rst7 from sMD trajectory |
| US array 29×11 ns | PASS | 30590 | 1 ns equil + 10 ns prod each; 290 ns total prod sampling |
| MBAR + bootstrap PMF | PASS | (login) | 50 bootstraps; PMF min = -5.08 kcal/mol at r=7.35 Å |
| Standard-state correction | PASS | (login) | Volume integral bound basin r∈[6,9] Å; ΔG_bind = -4.13 kcal/mol |

## Final result vs experiment
| Quantity | Computed | Experimental | ΔΔG |
|---|---|---|---|
| ΔG_bind | -4.13 kcal/mol | -6.4 kcal/mol (Ki=18 µM, Talhout 2001) | +2.3 kcal/mol |
| Bound r (BEN_COM–Asp189_Cα) | 7.35 Å (PMF min) | 7.38 Å (3PTB crystal) | < 0.1 Å |
| Doudou 2009 PMF (ff99SB) | -5.2 kcal/mol | -6.4 | +1.2 |

## Bugs/fixes encountered
- pdb4amber inserted TER at chymotrypsinogen numbering gaps → fixed with `--noter`
- Amber 80-char line limit truncated DISANG path → fixed with short relative path + local copy
- tleap `bond unit.resnum.atom` syntax needed PDB number not sequential idx (resolved by switching to pdb4amber + auto-SS via CONECT)
- pymbar 4 `FES.get_fes` index off-by-one → fixed with direct MBAR weights + manual histogram
- numpy 2 removed `np.trapz` → replaced with `np.trapezoid`

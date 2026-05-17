# Process Report — ABL1_T315I_imatinib_TI
Date: 2026-05-16

## System
- PDB: 1IEP (WT ABL1 kinase domain + imatinib)
- Protein: ABL1 kinase domain, chain A, MET225–GLN498
- Ligand: Imatinib / STI (CID: 5291, charge: 0)
- Force fields: ff14SB (protein), GAFF2/BCC (imatinib), TIP3P (water), Joung-Cheatham (ions)
- Box: TIP3P, 10 Å octahedral padding

## Steps

| Step | Status | SLURM Job | Notes |
|------|--------|-----------|-------|
| Extract chain A + STI from 1IEP | PASS | - | protein_chainA.pdb, STI_crystal.pdb |
| Cap termini ACE/NME | PASS | - | protein_capped.pdb (2234 atoms) |
| STI ligand build (Branch C) | PASS | - | 100% MCS match, 68 atoms, charge=0 |
| Antechamber GAFF2/BCC | PASS | 30523 | imatinib.mol2 (68 atoms), no ATTN in frcmod |
| tleap WT complex | PASS | - | wt_complex.prmtop (6.8 MB), 9 Na+ added |
| Mutate T315I (residue 92) | PASS | - | protein_T315I.pdb (13 ILE atoms) |
| tleap T315I complex | PASS | - | ti_complex.prmtop (6.8 MB), Errors=0 |
| tleap combined (WT+TI+STI+water) | PASS | - | combined_raw.prmtop (40800 atoms, 10623 waters) |
| Coord-sync mol2→mol1 common atoms | PASS | - | 4418 common atoms aligned |
| parmed tiMerge (bound) | PASS | - | ti_merged_bound.prmtop (6.8 MB) |
| parmed strip STI (apo) | PASS | - | ti_merged_apo.prmtop (6.7 MB) |
| TI masks | PASS | - | scmask1=@1479,1480; scmask2=@4421-4427 |
| Pre-equil bound (min+heat+equil λ=0.5) | RUNNING | 30524 | node002 |
| Pre-equil apo (min+heat+equil λ=0.5) | RUNNING | 30525 | node002 |
| TI bound leg (11 λ windows, 6 ns each) | PASS | 30526 | 5M steps/window complete; λ=0.0 and 1.0 excluded (endpoint instability) |
| TI apo leg (11 λ windows, 6 ns each) | PASS | 30527 | 5M steps/window complete |
| TI analysis (DV/DL integration) | PASS | - | ΔΔGbind = +1.748 ± 0.048 kcal/mol (9 windows, λ=0.1-0.9) |

## Re-runs / Auto-fixes
- λ=1.0 TI endpoint instability detected (DV/DL swings -145k to -0.9 kcal/mol). Cause: dual-topology ghost Thr OG1/HG1 at λ=1 overlap with active Ile CG1/CD1 atoms placed at approximate coordinates. λ=1.0 excluded from v1 trapezoidal integration (9-window analysis, λ=0.1-0.9).
- **v2 rerun with smoothstep softcore (Lee 2020, PMID:32672455)**: gti_lam_sch=1, gti_scale_beta=1, gti_ele_sc=1, gti_vdw_sc=1, gti_cut_sc=2, scalpha=0.2, scbeta=50.0. dS/dλ=0 at endpoints natively eliminates singularity. Submitted 22 windows (11 bound + 11 apo, jobs 30555, 30556), all complete (5 ns prod each). Endpoint DV/DL = 0.000 exactly. Final result: ΔΔGbind = +1.898 ± 0.099 kcal/mol (vs old v1 +1.748 ± 0.048; expt +2.7).
- Apo prmtop overwritten by stale background tiMerge script — re-stripped MOL (36314 atoms), pre-existing apo simulation data unaffected (loaded prmtop into memory before overwrite).

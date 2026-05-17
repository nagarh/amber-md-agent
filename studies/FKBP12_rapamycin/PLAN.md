# Simulation Plan — FKBP12 + Rapamycin

**Date:** 2026-05-14  
**Study:** `studies/FKBP12_rapamycin/`  
**Goal:** 50 ns explicit-solvent MD of FKBP12–rapamycin complex; MM-GBSA binding ΔG; per-residue decomposition top 5; compare vs experimental Kd.

---

## System Summary

| Item | Value |
|------|-------|
| PDB | 2DG3 (1.70 Å, clashscore 0.57, 0 missing residues) |
| Protein | FKBP12 (FK506-binding protein 12, 107 residues, chain A) |
| Ligand | Rapamycin (sirolimus) — HETATM `RAP`, C51H79NO13, MW 914, charge 0 |
| Remove | GOL (glycerol, crystallization artifact), HOH, alt locations |
| Experimental ΔG | −13.3 to −13.6 kcal/mol (Kd 0.13–0.2 nM, ChEMBL FKBP1A 2024) |
| Box | TIP3P octahedral, 12 Å padding |

---

## Force Fields

| Component | Force Field | Charges |
|-----------|-------------|---------|
| Protein | ff14SB | AMBER partial |
| Ligand (RAP) | GAFF2 | AM1-BCC (antechamber) |
| Water | TIP3P | — |
| Ions (Na⁺/Cl⁻) | Joung-Cheatham | — |
| PBRadii (GB) | mbondi2 | `set default PBRadii mbondi2` |

---

## Pipeline

### Phase 1 — Ligand Parametrization

Branch C (crystal HETATM, no hydrogens):

1. Fetch CCD ideal SDF for residue `RAP` from RCSB
2. Cross-validate formula/charge against PubChem "rapamycin" (CID 5284616)
3. Extract RAP HETATM from 2DG3 chain A only
4. MCS coordinate-transplant: CCD bond orders + crystal coordinates → AddHs
5. Submit antechamber GAFF2 BCC (`-nc 0`) to SLURM (~45 min)
6. parmchk2 → `rap.frcmod`; verify no `ATTN: need revision` missing params

> **Why Branch C, not rigid-body align:** PubChem conformer → rigid align gives 3.48 Å RMSD vs crystal. MCS transplant preserves crystal binding pose geometry.

### Phase 2 — System Build (tLEaP)

```
pdb4amber -i raw_pdbs/2DG3.pdb -o system/protein_clean.pdb \
    --remove-waters --no-conect --reduce
```

tLEaP script (`system/tleap.in`):
```
source leaprc.protein.ff14SB
source leaprc.water.tip3p
source leaprc.gaff2
loadAmberParams system/rap.frcmod
RAP = loadMol2 system/rap.mol2
set default PBRadii mbondi2
receptor = loadPDB system/protein_clean.pdb
complex = combine {receptor RAP}
solvateOct complex TIP3PBOX 12.0
addIons complex Na+ 0
addIons complex Cl- 0
saveAmberParm RAP system/lig.prmtop system/lig.inpcrd
saveAmberParm receptor system/rec.prmtop system/rec.inpcrd
saveAmberParm complex system/com.prmtop system/com.inpcrd
saveAmberParm complex system/com_solvated.prmtop system/com_solvated.inpcrd
quit
```

Produces 4 prmtops required by MMPBSA.py (§38.2.1 Amber manual).

### Phase 3 — MD Protocol

| Stage | Engine | Length | Key Parameters |
|-------|--------|--------|----------------|
| min1 | pmemd.cuda | 5000 steps | `imin=1`, restraint_wt=5.0 on `!:WAT,Na+,Cl-` |
| min2 | pmemd.cuda | 5000 steps | `imin=1`, no restraints |
| heat | pmemd.cuda | 20 ps | NVT, 0→300 K, Langevin γ=2.0, restraint_wt=5.0 |
| equil | pmemd.cuda | 500 ps | NPT, barostat=1 (Berendsen), taup=2.0, 300 K/1 atm |
| prod | pmemd.cuda | 50 ns | NPT, barostat=2 (MC), taup=1.0, ntwx=5000 (10 ps/frame) |

**Density gate after equil:** validate-step `--min-density 0.95`  
- ≥ 0.95 → production  
- < 0.95 → write-equil-density → 500 ps re-equil → production

**Timestep:** 2 fs throughout (`dt=0.002`, `ntc=2`, `ntf=2`, SHAKE on H)  
**PME cutoff:** 10.0 Å (`cut=10.0`)  
**Output:** NetCDF (`ioutfm=1`), snapshots every 10 ps

### Phase 4 — MM-GBSA

**Protocol:** Single-trajectory (extract rec + lig from complex traj)

**ante-MMPBSA.py** (strip solvent, generate dry prmtops):
```bash
ante-MMPBSA.py -p com_solvated.prmtop \
    -c com.prmtop -r rec.prmtop -l lig.prmtop \
    -s ':WAT,Na+,Cl-' --radii mbondi2
```

**MMPBSA.py input** (`analysis/mmpbsa.in`):
```
&general
  startframe=101, endframe=500, interval=1,
  keep_files=1,
/
&gb
  igb=2, saltcon=0.15, gbsa=1,
/
&decomp
  idecomp=2, dec_verbose=3,
  print_res="1-107",
/
```

- **Frames:** 101–500 (skip first 10 ns = 100 frames; use 400 frames × 100 ps = 40 ns)
- **igb=2** (mbondi2 radii) — standard for hydrophobic binding pocket (FKBP12)
- **idecomp=2** — per-residue: 1-4 EEL→EEL, 1-4 VDW→VDW
- **saltcon=0.15** — physiological ionic strength

**Expected output:**
- `FINAL_DECOMP_MMPBSA.dat` — per-residue ΔG contributions
- Top 5 residues by |ΔG_decomp| → structural interpretation

**Comparison target:** ΔG_exp = −13.3 to −13.6 kcal/mol  
*(Note: MM-GBSA systematically overestimates magnitude; typical error ±2–4 kcal/mol)*

### Phase 5 — cpptraj Analysis

```
# RMSD backbone vs crystal frame 1
rmsd :1-107@CA,C,N first out analysis/bb_rmsd.dat
# Ligand RMSD vs crystal frame 1
rmsd :108@C,N,O,S first out analysis/lig_rmsd.dat nofit
# RMSF per residue
atomicfluct :1-107@CA out analysis/rmsf.dat byres
```

---

## File Organization

```
studies/FKBP12_rapamycin/
├── raw_pdbs/
│   └── 2DG3.pdb
├── system/
│   ├── build_ligand.py       ← Branch C script
│   ├── ligand_ready.sdf      ← RAP with H
│   ├── rap.mol2, rap.frcmod  ← GAFF2 params
│   ├── protein_clean.pdb     ← pdb4amber output
│   ├── tleap.in
│   ├── leap.log
│   ├── com_solvated.prmtop/inpcrd
│   ├── com.prmtop, rec.prmtop, lig.prmtop
├── simulations/
│   ├── min1/, min2/, heat/, equil/, prod/
├── analysis/
│   ├── mmpbsa.in
│   ├── cpptraj_analysis.in
│   ├── bb_rmsd.dat, lig_rmsd.dat, rmsf.dat
│   ├── FINAL_DECOMP_MMPBSA.dat
│   └── plots/
├── logs/                     ← SLURM .out/.err
├── PLAN.md                   ← this file
├── PROCESS_REPORT.md         ← engineering log (live)
└── STUDY_REPORT.md           ← scientific findings (post-analysis)
```

---

## Validation Gates

| Gate | Tool | Pass Criterion |
|------|------|----------------|
| tLEaP | validate-tleap leap.log | Errors = 0 |
| After equil | validate-step equil.mdout | density ≥ 0.95 g/cc |
| After prod | validate-step prod.mdout | NSTEP = 25000000, no NaN energy |
| antechamber | grep Total charge | must = 0.00 |
| parmchk2 | grep "ATTN" rap.frcmod | no ATTN lines |

---

## Compute Estimates

| Job | Partition | Time |
|-----|-----------|------|
| antechamber BCC | defq, 0 GPU | ~45 min |
| min1 + min2 + heat | defq, 1 GPU | ~15 min total |
| equil 500 ps | defq, 1 GPU | ~20 min |
| prod 50 ns | defq, 1 GPU | ~18–24h |
| MMPBSA.py 400 frames | defq, 0 GPU | ~1–2h |
| cpptraj | login node | ~5 min |

**Total wallclock: ~24–30h** (dominated by production MD)

---

## Experimental Reference

| Source | Value | Units | ΔG (kcal/mol) |
|--------|-------|-------|---------------|
| ChEMBL CHEMBL5629796 (2024) | 0.13 | nM Kd | −13.57 |
| ChEMBL CHEMBL5506186 (2024) | 0.20 | nM Kd | −13.31 |
| ChEMBL CHEMBL3369573 (2014) | 0.20 | nM Kd | −13.31 |

ΔG computed as RT·ln(Kd_M) at 300 K. Sign: negative = favorable binding.

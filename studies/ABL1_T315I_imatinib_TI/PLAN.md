# Plan — ABL1_T315I_imatinib_TI
Date: 2026-05-16

## Objective
Compute ΔΔGbind for the T315I gatekeeper mutation in ABL1 kinase with imatinib using Thermodynamic Integration (TI). Quantify the molecular origin of 100-fold (ΔΔGbind ≈ 2.7 kcal/mol) affinity loss observed experimentally.

## Thermodynamic Cycle

```
WT-ABL1:Imatinib  --ΔGmut,bound(λ: 0→1)--> T315I-ABL1:Imatinib
WT-ABL1           --ΔGmut,apo(λ: 0→1)---> T315I-ABL1

ΔΔGbind = ΔGmut,bound - ΔGmut,apo
Expected: ~2.7 kcal/mol (from 100-fold Kd loss = RT·ln(100))
```

## System (from preflight)
- PDB: 1IEP (WT ABL1 kinase domain + imatinib, 2.1 Å)
- Biological unit: MONOMERIC — use chain A only
- Chain A: MET225–GLN498 (truncated construct, normal for ABL1 kinase domain)
- Ligand: STI (imatinib), residue 201 chain A, 74 heavy atoms, formal charge = 0
- Chloride ions (CL): crystallographic artifacts — excluded
- Crystal waters: removed, TIP3P solvated fresh
- Missing residues: GLY223-ALA224 (pre-start), GLU499–THR515 (post-end) — all terminal, handled by ACE/NME capping
- T315 confirmed present: THR A 315

## Force fields
| Component | FF | Reason |
|-----------|----|--------|
| Protein | ff14SB | Standard kinase studies |
| Ligand STI | GAFF2/BCC | Published standard for imatinib-type compounds |
| Water | TIP3P | Matches Joung-Cheatham ions, fast GPU |
| Ions | Joung-Cheatham | Matches TIP3P water model |

## Protonation states (pH 7.0)
| Residue | State | Rationale |
|---------|-------|-----------|
| All HIS residues | HIE (default) | No active-site HIS in ABL1 kinase, pH 7 default |
| All other residues | Standard | No unusual pKa residues near binding site |
(Non-default residues only. Standard tleap protonation.)

## TI Mutation: T315 → I315

**Atoms common to both states** (backbone + CB + CG2-methyl):
N, H, CA, HA, CB, HB, CG2, 1HG2, 2HG2, 3HG2, C, O

**scmask1** (Thr-unique, disappear at λ=1): OG1, HG1 — 2 atoms
**scmask2** (Ile-unique, appear at λ=1): CG1, HG11, HG12, CD1, HD11, HD12, HD13 — 7 atoms

## System Build Protocol

### Step A — Structure preparation
```
1. Clean 1IEP → chain A + STI only (remove chain B, CL, HOH)
2. Cap termini: ACE at N-term (before MET225), NME at C-term (after GLN498)
3. Parametrize STI: amber-ligand.md Branch C pipeline
   → ligand_ready.sdf → antechamber GAFF2 → STI.mol2, STI.frcmod
```

### Step B — WT system build
```
4. tLEaP: ff14SB + GAFF2 + TIP3P
   - Box: 10 Å octahedral TIP3P
   - Neutralize with Joung-Cheatham Na+/Cl-
   → wt_complex.prmtop, wt_complex.inpcrd (protein + STI + water)
```

### Step C — T315I system build
```
5. Mutate residue 315 Thr→Ile in cleaned PDB (replace OG1/HG1 with CG1/2H, add CD1/3H)
   Python script using RDKit/BioPython to swap side chain atoms at residue 315
6. tLEaP: SAME number of water molecules + SAME box as WT (copy wt water box, just update residue 315)
   → ti_complex.prmtop, ti_complex.inpcrd
```

### Step D — Combined TI prmtop (tiMerge)
```
7. Create combined prmtop using Python/parmed:
   combined = wt_protein_only + ti_protein_only (no water, no STI yet)
   Add STI and water back → ti_combined.prmtop

8. Run ParmEd tiMerge:
   parmed -p ti_combined.prmtop -i merge.in
   merge.in:
     loadRestrt ti_combined.inpcrd
     tiMerge :1-<N_wt_residues> :<N_wt_residues+1>-<2N_residues> :<wt_315_resnum> :<ti_315_resnum>
     outparm ti_merged.prmtop ti_merged.inpcrd

9. For apo leg: strip STI from ti_merged.prmtop → ti_merged_apo.prmtop

tiMerge outputs the exact timask1/timask2/scmask1/scmask2 atom indices for mdin files.
```

## Simulation Protocol

### Pre-equilibration (WT complex only, use output for all λ windows)

| Step | Ensemble | Restraints | dt | Length |
|------|----------|------------|----|--------|
| Min1 | — | 10 kcal/mol·Å² backbone | — | 5000 cyc |
| Min2 | — | none | — | 10000 cyc |
| Heat | NVT, Langevin γ=2 | 5 kcal/mol·Å² | 2 fs | 100 ps, 0→300 K |
| Equil | NPT, Berendsen taup=2.0 | 0.5 kcal/mol·Å² | 2 fs | 500 ps |

Output: equil.rst7 → starting point for ALL λ windows.

### TI mdin settings (each λ window)

```fortran
&cntrl
  imin=0, nstlim=5000000, irest=1, ntx=5,
  dt=0.001,                     ! 1 fs — REQUIRED with tishake=1
  ntt=3, temp0=300.0, gamma_ln=2.0, ig=-1,
  ntb=2, ntp=1, barostat=2, taup=5.0, pres0=1.0,
  cut=10.0,
  ntc=2, ntf=1,
  tishake=1,                    ! remove SHAKE on SC bonds (requires 1 fs dt)
  ntpr=1000, ntwx=5000, ntwr=500000, ntwe=1000,
  ioutfm=1, iwrap=1,
  icfe=1, ifsc=1,               ! TI with softcore
  clambda=LAMBDA,               ! set per window: 0.0,0.1,...,1.0
  scalpha=0.5, scbeta=12.0,
  gti_add_sc=1,                 ! correct 1-4 non-bonded terms (Amber20+ fix)
  gti_bat_sc=1,                 ! correct bonded terms at SC/CC boundary
  gti_syn_mass=1,
  timask1='MASK1', timask2='MASK2',   ! from tiMerge output
  scmask1='SCMASK1', scmask2='SCMASK2',
  ifmbar=1,
  mbar_states=11,
  mbar_lambda=0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
/
```

### Lambda schedule
11 windows: λ = 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0
Each window: 5 ns production (after 1 ns equilibration per window)
Source: skill default for TI (5 ns × N λ)

### TI execution
- **Bound leg**: 11 windows × 6 ns (1 ns equil + 5 ns prod) = SLURM array job, ti_bound/
- **Apo leg**: 11 windows × 6 ns = SLURM array job, ti_apo/
- Both legs run on ti_merged.prmtop / ti_merged_apo.prmtop respectively

## Box
- Model: TIP3P
- Padding: 10 Å octahedral
- Ions: Joung-Cheatham, neutralize to 0 charge (imatinib charge=0, neutralize protein charge only)

## Analysis targets
1. DV/DL vs λ curves for bound and apo legs
2. Trapezoidal integration → ΔGmut,bound, ΔGmut,apo
3. MBAR cross-validation (pymbar or Amber MBAR output)
4. ΔΔGbind = ΔGmut,bound - ΔGmut,apo
5. Compare to experimental ΔΔGbind ≈ 2.7 kcal/mol (100-fold Kd loss)
6. Decompose: H-bond contribution (OG1 disappears) vs steric contribution

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim type | Key result |
|------------------------|--------|----------|------------|
| Tse & Verkhivker 2015, PMID:26075886, doi:10.1371/journal.pone.0130203 | ABL1 + imatinib/nilotinib/bosutinib | Comp alanine scanning + network analysis | H-bond at T315 is energetic hot spot |
| Kim et al. 2021, PMID:32510566, doi:10.1093/bib/bbaa108 | Kinase gatekeeper mutations landscape | Structural/statistical | T315 is top DR hotspot across 538 kinases |
| Nussinov et al. 2022, PMID:34693559, doi:10.1002/med.21863 | ABL1 gatekeeper mechanisms | Review | DFG-out conformational shift drives resistance |
No published TI protocol for this exact system found — defaults are skill-based.

## Walltime estimates
System ~225 residues + imatinib + ~15k waters ≈ 50k atoms
pmemd.cuda at 50k atoms: ~150 ns/day with 2 fs dt; with 1 fs dt → ~75 ns/day
Per window: 6 ns / 75 = 0.08 days ≈ 2 hours → walltime 4 hours per window
Total: 22 windows × 4 h = ~88 h GPU time (parallel SLURM array)

| Job set | Windows | Walltime each | Parallel |
|---------|---------|---------------|----------|
| Pre-equil (WT) | 1 | ~1 h | — |
| TI bound | 11 | 4 h | yes (array 0-10) |
| TI apo | 11 | 4 h | yes (array 0-10) |

## Caveats / limitations
- Single-topology protein mutation via tiMerge — standard Amber approach but complex build
- 5 ns/window adequate for this small perturbation (2-7 atoms); extend if DV/DL variance high
- 1 fs timestep (tishake=1) doubles compute time vs 2 fs; required for SC bond accuracy
- TIP3P water: overestimates diffusion, acceptable for binding ΔΔG calculations
- DFG-out conformation stabilized by imatinib in crystal — TI assumes this conformation maintained throughout
- No enhanced sampling: conformational changes at longer timescales not captured
- Starting from crystal structure: may have crystal lattice bias in initial geometry

## Approval: APPROVED 2026-05-16

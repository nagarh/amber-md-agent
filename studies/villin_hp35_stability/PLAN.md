# Plan — villin_hp35_stability
Date: 2026-05-17

## System (from preflight)
- PDB: 2RJY, monomeric
- Organism: Gallus gallus (chicken) villin-1 headpiece subdomain (HP67)
- Biological unit: MONOMERIC (1 chain, 1 BIOMT operator)
- Chains kept: A (residues 13–76, 64 resolved residues)
- Residues 10–12 (PRO, THR, LYS) missing from electron density — N-terminal disordered tail, not loop-modeled
- Atom count (protein only, capped): 518 atoms; solvated estimate ~20,000–24,000 atoms (TIP3P 12 Å box)
- Special features: truncated construct (starts at LEU13) → ACE/NME caps applied; 1 HIS residue (HIS41, non-default protonation — see below)
- Disulfides: none
- Ligands: none
- Crystal resolution: 1.40 Å

## Force fields
| Component | FF | Reason |
|-----------|----|--------|
| Protein | ff14SB | Validated for helical peptides (Maier et al. 2015, PMID:26574453) |
| Water | TIP3P | Standard; matches Joung-Cheatham ions |
| Ions | Joung-Cheatham (leaprc.water.tip3p loads these) | Parameterized for TIP3P |

## Protonation states (at pH 7.0)
| Residue | State | propka pKa | Rationale |
|---------|-------|------------|-----------|
| HIS 41 A | HID | 6.52 | 6.0–8.0 range → neutral; ND1 is H-bond donor to GLU14 carboxylate O at 2.81 Å → H on Nδ → HID |

All other ionizable residues at standard state:
- 5× ASP (19, 28, 34, 44, 46): all pKa 2.93–4.00 < 7 → deprotonated ASP ✓
- 5× GLU (14, 27, 39, 45, 72): all pKa 4.18–4.79 < 7 → deprotonated GLU ✓
- 6× LYS (38, 48, 65, 70, 71, 73): pKa 9.9–10.4 > 7 → protonated LYS+ ✓
- 3× ARG (31, 37, 55): pKa ~12.4–13.0 > 7 → protonated ARG+ ✓
- Net charge: +6(LYS) + 3(ARG) − 5(ASP) − 5(GLU) = **−1** → 1 Na+ added to neutralize

## Simulation protocol
| Step | Setting | Time / cycles | Source |
|------|---------|---------------|--------|
| Min1 | NMask restraint on backbone (ntr=1), 10 kcal/mol·Å² | 5000 cyc | skill default |
| Min2 | Unrestrained full | 10000 cyc | skill default |
| Heat | NVT 0→300 K, Langevin γ=2 ps⁻¹, backbone restrained 5 kcal/mol·Å² | 100 ps | skill default |
| Burst density | NPT, Berendsen barostat=1, taup=0.5, no restraint | until mean 0.95–1.05 g/cc + fluct < 0.02 | skill default |
| Equil2 | NPT, Berendsen barostat=1, taup=2.0, 0.5 kcal/mol·Å² backbone restraint | 250 ps | skill default (small <50k atoms) |
| Production | NPT, MC barostat=2, taup=5.0, no restraint | **1 ns** | user |

### Production mdin details
- nstlim = 500000 (× dt=0.002 ps = 1 ns)
- ntwx = 1000 → save frame every 2 ps → 500 frames total
- ntpr = 1000 → mdout line every 2 ps
- ntwr = 50000

## Box
- Solvent: TIP3P, padding 12 Å (standard, protein diameter ~30 Å → box side ~54 Å, well above 2× cutoff=20 Å)
- Ions: Joung-Cheatham, neutralize-only (addIons Na+ 0; addIons Cl- 0)
- Estimated ion count: 1 Na+

## Analysis targets
- Backbone RMSD (Cα, C, N) vs. crystal structure
- Per-residue RMSF (Cα, byres)
- Energy/temperature/density from read_mdout
- Convergence check: check_convergence(rmsd.dat)

**Expected outcomes (literature precedent):**
- Backbone RMSD: ~1–2 Å from crystal (stable folded state at 300 K, 1 ns)
- RMSF: helix regions < 1 Å; N/C-terminal caps and loop ~1.5–3 Å
- Temperature: 300 ± 5 K
- Density: 1.00–1.02 g/cc (TIP3P)

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable |
|------------------------|--------|------------|-----|----------------|
| Nijhawan et al. 2025, PMID:40192555, DOI:10.1002/cphc.202500049 | HP35 villin headpiece + 2F4K mutant | Equilibrium MD + X-ray scattering | — | HP35 two-state unfolding; stable at 300 K, RMSD ~1–2 Å |
| Zou et al. 2024, PMID:38649777, DOI:10.1038/s41598-024-59780-3 | HP35 free (control) + on fluorinated graphene | MD | — | Native HP35 RMSD < 2 Å; denaturation > 3 Å on nanomaterial |

Defaults align with published practice for villin headpiece stability. 1 ns = folded-state fluctuations only (folding timescale ~0.7 µs; caveat noted below).

## Method best practices
Standard MD — Step 2c skipped (no alchemical/enhanced-sampling/MMPBSA keywords).

## Walltime estimates
| System size | GPU ns/day estimate | This study |
|-------------|---------------------|------------|
| ~20k atoms, 1 GPU (pmemd.cuda) | ~100–200 ns/day | min+heat: ~15 min; equil2: ~5 min; prod 1 ns: ~10–15 min; total ~35 min |

## Caveats / limitations
- 1 ns << folding timescale (~0.7 µs); this study measures folded-state stability only
- HP67 construct (res 13–76), not HP35 — includes extra N-terminal helix; slightly different literature coverage vs. HP35
- Single replicate; no replica exchange or enhanced sampling
- TIP3P slightly over-structures water; density ~1.02 g/cc expected
- Crystal contacts absent in simulation; box edge effects negligible at 12 Å padding

## Approval: APPROVED 2026-05-17

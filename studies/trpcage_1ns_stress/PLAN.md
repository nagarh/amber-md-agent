# Plan — trpcage_1ns_stress
Date: 2026-05-17

## System (from preflight)
- PDB: 1L2Y, monomeric (chain A only; no REMARK 350 present)
- Biological unit: monomer (single 20-residue Trp-cage miniprotein)
- Chains kept: A
- Atom count (estimated): ~304 protein atoms + ~4,500 TIP3P waters + ions ≈ ~14,000 atoms total (12 Å box)
- Special features: none (no ligands, no disulfides, no modified residues, full-length N/C termini)

## Force fields
| Component | FF | Reason |
|-----------|----|--------|
| Protein | ff14SB | Well-validated for small structured proteins with TIP3P |
| Water | TIP3P | Matches ff14SB parametrization; standard for stress test |
| Ions | Joung-Cheatham | Matches TIP3P water model |

## Protonation states (at pH 7.0)
Standard protonation for all residues. No non-default states required.
| Residue | State | Rationale |
|---------|-------|-----------|
| ASP9 | ASP | pKa ~3.9, fully deprotonated at pH 7 |
| LYS8 | LYS | pKa ~10.5, protonated at pH 7 |
| ARG16 | ARG | pKa ~12.5, protonated at pH 7 |

## Simulation protocol
| Step | Setting | Time / cycles | Source |
|------|---------|---------------|--------|
| Min1 | restrained backbone, 10 kcal/mol·Å² | 5000 cyc | skill default |
| Min2 | full unrestrained | 10000 cyc | skill default |
| Heat | NVT 0→300 K, Langevin γ=2, restrained 5 kcal/mol·Å² | 100 ps | skill default |
| Burst density | NPT, Berendsen barostat=1, taup=0.5, no restraint | until mean 0.95–1.05 g/cc + fluct < 0.02 | skill default |
| Equil2 | NPT, Berendsen barostat=1, taup=2.0, restrained 0.5 kcal/mol·Å² | 250 ps | skill default (small system <50k atoms) |
| Production | NPT, MC barostat=2, taup=5.0, no restraint | 1 ns (500,000 steps × 2 fs) | user (study name) |

## Box
- Solvent: TIP3P, padding 12 Å
- Ions: Joung-Cheatham, neutralize-only (Trp-cage net charge: +2 from LYS8 + ARG16 - ASP9 → add 2 Cl⁻)

## Analysis targets
- Backbone RMSD (Cα,C,N) vs initial
- Per-residue RMSF by Cα
- Temperature and density averages from prod.mdout
- Convergence check (RMSD plateau, last 50% drift < 0.5 Å)

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable / value |
|------------------------|--------|------------|-----|------------------------|
| Hao et al. 2015, PMID:26492886, DOI:10.1038/srep15568 | Trp-cage miniprotein | Variable (MSA-MD) | Not ff14SB | Folding to native state identified |
| Bousova et al. 2021, PMID:33969912, DOI:10.1002/pro.4107 | Trp-cage fusion chimeras | NS range | CHARMM-based | RMSD stability ~1 Å from crystal |

No directly comparable published value for 1ns explicit TIP3P/ff14SB Trp-cage — both papers use non-standard protocols or different FF.
Defaults are skill-validated; expected backbone RMSD ~1–2 Å for stable Trp-cage fold.

## Method best practices (from Step 2c)
Standard MD — Step 2c skipped. No alchemical/REMD/enhanced-sampling/mutation keywords detected.

## Walltime estimates
| System size | ns/day (GPU estimate) | This study walltime |
|-------------|-----------------------|---------------------|
| ~14k atoms (small) | 100–200 ns/day on GPU | min+heat ~20 min, equil2 ~15 min, prod ~15 min; total ~1 hr |

Request 2 hr walltime with safety margin.

## Caveats / limitations
- 1 ns insufficient to observe Trp-cage folding/unfolding events (µs timescale); this is a stability/stress test only
- Single replicate, no enhanced sampling
- TIP3P overestimates protein rigidity slightly vs OPC — acceptable for smoke test
- GPU advantage marginal at ~14k atoms per manual p.461 (may run near CPU/GPU threshold)

## Approval: APPROVED 2026-05-17

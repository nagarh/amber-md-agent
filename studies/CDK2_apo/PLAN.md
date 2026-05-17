# Plan — CDK2_apo
Date: 2026-05-15

## System (from preflight)
- PDB: 4EK3 (Crystal structure of apo CDK2, 1.34 Å — highest resolution apo CDK2 available)
- Biological unit: MONOMERIC (chain A only)
- Chains kept: A
- Atom count (estimated): ~55,000 (protein ~4,500 heavy + H, TIP3P water, ions)
- Special features:
  - N-terminus already ACE-capped in crystal (residue 0)
  - Loop 37-44 (LDTETEGV) universally disordered in all CDK2 crystal structures — grafted from AlphaFold P24941 (mean pLDDT ~63, surface loop, distal from hinge/activation loop) [DEFAULT — low-confidence region noted]
  - C-terminal residues 297-298 missing (terminal, NME-handled by tLEaP)
  - Alternate conformers → pdb4amber kept only 'A' conformer
  - No ligands, no metals, no disulfides

## Force fields
| Component | FF | Reason |
|-----------|----|--------|
| Protein | ff14SB | Standard for folded proteins, well-validated for kinases |
| Water | TIP3P | Recommended for ff14SB; standard in CDK2 literature |
| Ions | Joung-Cheatham | Parameterized for TIP3P |

## Protonation states (at pH 7)
| Residue | State | Rationale |
|---------|-------|-----------|
| HIS60 | HID | Solvent exposed, standard |
| HIS71 | HID | Solvent exposed, standard |
| HIS84 | HID | Hinge region, backbone key for ATP binding; sidechain solvent-accessible at pH 7, no H-bond donors/acceptors to shift pKa |
| HIS119 | HID | Standard |
| HIS121 | HID | Standard |
| HIS125 | HID | Standard |
| HIS161 | HID | Near activation loop (Thr160 phosphorylation site), solvent accessible |
| HIS268 | HID | Standard |
| HIS283 | HID | Standard |
| HIS295 | HID | C-terminal, standard |
(All HIS → HID: pdb4amber default; appropriate for solvent-exposed His at physiological pH. No catalytic or buried His in CDK2 apo form requiring HIP/HIE reassignment.)
| All ASP/GLU | standard (deprotonated) | pH 7 >> pKa ~4.0 |

## Simulation protocol
| Step | Setting | Time / cycles | Source |
|------|---------|---------------|--------|
| Min1 | restrained backbone, 10 kcal/mol·Å² | 5000 cyc | skill default |
| Min2 | full system | 10000 cyc | skill default |
| Heat | NVT 0→300 K, Langevin γ=2, backbone restrained 5 kcal/mol·Å² | 100 ps | skill default |
| Burst density | NPT, Berendsen barostat=1, taup=0.5, no restraint | until mean 0.95–1.05 g/cc + fluct < 0.02 | skill default |
| Equil2 | NPT, Berendsen barostat=1, taup=2.0, backbone restrained 0.5 kcal/mol·Å² | 500 ps | skill default (medium system) |
| Production | NPT, MC barostat=2, taup=5.0, no restraint | **20 ns** | user request |

### Production length note
User specified 20 ns. **CAVEAT**: Activation loop full DFG-flip and inactive→active transitions in CDK2 apo require μs timescales. 20 ns will characterize local fluctuations, hinge breathing, and partial activation loop excursions — but not rare-event conformational transitions.

## Box
- Solvent: TIP3P, padding 12 Å (standard for folded monomeric kinase)
- Ions: Joung-Cheatham, neutralize-only (CDK2 has net charge; add Na+/Cl- as needed)

## Analysis targets
1. Backbone RMSD (all Cα) — convergence check
2. Per-residue RMSF (Cα) — global and zoomed on functional regions
3. Hinge region flexibility: RMSF of residues 80–90 (E81, L83, H84 are key ATP H-bond contacts)
4. Activation loop flexibility: RMSF of residues 145–172 (DFG: D145-F146-G147; T160 phosphorylation site)
5. αC helix flexibility: RMSF of residues 45–60 (PSTAIRE motif, cyclin binding interface)
6. Lys33–Glu51 distance (αC helix salt bridge — marker of active/inactive state; active: ~3.5 Å)
7. DFG-Asp145 Cα–Phe146 Cβ–Gly147 Cα backbone angle (DFG conformation monitoring)

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable / value |
|------------------------|--------|------------|-----|------------------------|
| Zhang W et al. 2024, PMID:38818077, DOI:10.1021/jacsau.4c00138 | CDK2 and CDK4 active complexes, MD + modeling | ns-scale | Not specified | Activation loop as key switch; CDK4 more dynamic than CDK2 in ATP binding site and regulatory spine; αC helix allosteric regulation |
| Bravo-Moraga F et al. 2025, PMID:40321554, DOI:10.1021/acsomega.5c00555 | CDK2 + roniciclib (inhibitor-bound) | ns-scale | Not specified | Key residues Phe80, Lys33, Asp145 maintain binding; 2 unbinding pathways via αD and β1/β2 segments |
| Ziada S et al. 2024, PMID:38791449, DOI:10.3390/ijms25105411 | CDK8-CycC MD | Full MD | AMBER ff | CycC stabilizes CDK8; activation loop as molecular switch; Glu99 CycC role in activation |

No direct apo CDK2 20 ns simulation found in PubMed search. Closest analogies from CDK family simulations above. Defaults are skill-derived with kinase literature context.

## Walltime estimates
| System size | ns/day (GPU) | This study walltime |
|-------------|--------------|---------------------|
| ~55k atoms (medium) | ~150–250 ns/day | Min+heat ~30 min, equil2 ~30 min, prod ~2–4 hr |

## Caveats / limitations
- **Sampling**: 20 ns insufficient for rare activation loop events (DFG flip, inactive→active transition requires μs). Will characterize local fluctuations only.
- **Single replicate**: No statistical replicates — cannot quantify sampling uncertainty.
- **Apo form**: No cyclin A or ATP present — activation state not physiological; represents inactive T-loop conformation (Thr160 unphosphorylated).
- **Modeled loop 37-44**: AlphaFold grafted, pLDDT ~63, surface loop distal from hinge/activation loop — low impact on results.
- **TIP3P water**: Overestimates water diffusion; adequate for structural dynamics at this timescale.
- **No enhanced sampling**: Plain MD; slow conformational changes will not be sampled.

## Approval: APPROVED 2026-05-15

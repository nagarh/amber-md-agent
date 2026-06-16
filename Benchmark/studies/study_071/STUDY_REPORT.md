# Study Report — BPTI (5PTI) Structural Stability, 100 ns Explicit-Solvent MD at 300 K
Date: 2026-06-09

## 1. Objective
Assess the structural stability of bovine pancreatic trypsin inhibitor (BPTI, PDB 5PTI) in explicit
water at 300 K over a 100 ns molecular-dynamics trajectory, and quantify deviation from the crystal
structure via backbone RMSD. BPTI is a 58-residue Kunitz-type serine-protease inhibitor rigidified by
three disulfide bonds; it is one of the longest-standing reference systems in biomolecular simulation.
This is a **stability check** (not a binding or rare-event study): the expectation is a low, plateaued
backbone RMSD (~1–2 Å) confirming the native fold is maintained, with flexibility limited to chain
termini and surface loops.

## 2. System
- PDB: 5PTI, monomeric (REMARK 350: single operator, chain A)
- Chains kept / construct: chain A only, residues 1–58, full-length (no missing residues, no capping)
- Atom count: 18,502 total (454 protein heavy atoms + rebuilt H; 4,395 OPC waters; 6 Cl⁻)
- Box: OPC truncated octahedron, 10 Å padding, ~59.8 Å edge, volume ~140,100 Å³ (prod.mdout AVERAGES)
- Ligand: none — apo. PO4 (phosphate buffer), UNX (1 unidentified atom), DOD (crystallographic D2O) all stripped
- Special features:
  - 3 disulfide bonds: Cys5–Cys55, Cys14–Cys38, Cys30–Cys51 (CYS→CYX + CONECT records)
  - 5PTI is a joint X-ray/neutron structure (1.0 Å) containing **deuterium** atoms; all D/H stripped, protons rebuilt by tLEaP
  - Alternate conformers GLU7, MET52 → kept higher-occupancy conformer A

## 3. Protonation Rationale
pH 7.4 (BPTI is a secreted/extracellular Kunitz inhibitor; extracellular compartment). propka3 was run on
the starting structure (system/protein_cyx.pka). All titratable residues fall far from pH 7.4, so all
adopt standard states — no overrides applied. BPTI contains no histidine.

| Residue | State | pKa context | Rationale |
|---------|-------|-------------|-----------|
| ASP3, ASP50 | deprotonated (standard) | propka3 pKa 3.7–3.85 | pKa ≪ 7.4 |
| GLU7, GLU49 | deprotonated (standard) | propka3 pKa 4.86–5.37 | pKa ≪ 7.4 |
| LYS15/26/41/46 | protonated (standard) | propka3 pKa 10.1–10.6 | pKa ≫ 7.4 |
| ARG1/17/20/39/42/53 | protonated (standard) | propka3 pKa 11.8–12.6 | pKa ≫ 7.4 |
| TYR10/21/23/35 | protonated (standard) | propka3 pKa ~10 | pKa ≫ 7.4 |
| Cys5/14/30/38/51/55 | CYX (disulfide) | not titratable | 3 SS bonds from SSBOND records |

## 4. Methods (actual values from executed mdin files)

| Step | Ensemble | Thermostat | Barostat | dt | cut | SHAKE | Restraints | Length |
|------|----------|------------|----------|----|----|-------|------------|--------|
| Min1 | — | — | — | — | 10 Å | — | 10 kcal/mol·Å² @CA,C,N | 5000 cyc (ncyc=2500) |
| Min2 | — | — | — | — | 10 Å | — | none | 5000 cyc (conv. 4873) |
| Heat | NVT | Langevin γ=5.0 | — | 2 fs | 10 Å | H-bonds (ntc=2) | 10 kcal/mol·Å² @CA,C,N | 100 ps, 0→300 K (nmropt TEMP0 ramp) |
| Burst (equil) | NPT | Langevin γ=5.0 | Berendsen taup=2.0 | 2 fs | 10 Å | H-bonds | 5 kcal/mol·Å² @CA,C,N | 200 ps |
| Equil2 | NPT | Langevin γ=5.0 | MC (barostat=2) | 2 fs | 10 Å | H-bonds | none | 500 ps |
| Prod | NPT | Langevin γ=5.0 | MC (barostat=2) | 2 fs | 10 Å | H-bonds | none | **100 ns** (50,000,000 steps) |

## 5. Results
Every value cites a file.

| Observable | Mean ± std | Range | Source |
|------------|------------|-------|--------|
| Backbone RMSD vs crystal (@C,CA,N, mass-wt) | 1.057 ± 0.190 Å | 0.724–1.678 Å | analysis/rmsd_backbone.dat |
| Backbone RMSD, last 50 ns | 0.968 ± 0.116 Å | — | analysis/rmsd_backbone.dat |
| RMSF backbone (per residue) | 0.703 Å mean | min 0.36 Å (res23); max 3.54 Å (res58 C-term) | analysis/rmsf_byres.dat |
| Radius of gyration | 11.11 ± 0.08 Å | 10.86–11.37 Å | analysis/radgyr.dat |
| Density | 1.0195 g/cc | 1.011–1.028 g/cc | prod.mdout AVERAGES |
| Temperature | 300.01 K | — | prod.mdout AVERAGES |
| Energy (Etot) | -48,196.7 kcal/mol | — | prod.mdout AVERAGES |

Plots: analysis/rmsd_backbone.png, analysis/rmsf_byres.png

## 6. Convergence Assessment
| Observable | drift_abs | threshold | status |
|------------|-----------|-----------|--------|
| Backbone RMSD | 0.178 Å (first-half 1.146 → second-half 0.968) | 0.5 Å | converged |

Threshold justification: a ~0.5 Å backbone-RMSD drift between trajectory halves is the standard heuristic
guardrail for a plateaued folded-protein trajectory (check_convergence default; Tier 3 — no tighter
system-specific precedent needed for a rigid disulfide-locked protein). Observed drift (0.178 Å) is well
below it; RMSD in fact decreases slightly over time, settling closer to the crystal. Block-averaging SEM
remains small (≤0.049 Å up to block size 500), consistent with a converged equilibrium fluctuation.

## 7. Key Findings
- **BPTI maintains its native fold throughout 100 ns**: backbone RMSD vs crystal averages 1.06 Å (0.97 Å over the last 50 ns), never exceeding 1.68 Å (§5) — the canonical signature of a stable folded simulation.
- **The trajectory is converged and the fold is rigid**: RMSD drift between halves is only 0.18 Å (§6) and Rg is essentially constant at 11.11 ± 0.08 Å (§5), i.e. no expansion or collapse of the compact disulfide-locked core.
- **Flexibility is confined to chain termini and one surface loop**: backbone RMSF is lowest in the core (0.36 Å at res23) and rises only at the C-terminus (3.54 Å at res58, 1.55 Å at res57) and the 12–13 loop (~1.1–1.3 Å) (§5) — consistent with the three disulfide bonds rigidifying the interior.
- **The simulation is physically well-behaved**: T = 300.0 K and density = 1.02 g/cc held stable with no energy drift or NaN (§5), confirming the ff19SB/OPC setup and NPT protocol are sound.

## 8. Caveats & Limitations
- **Single 100 ns replicate**: a stability assessment, not an exhaustive conformational ensemble. No replica exchange / enhanced sampling; slow rare events (e.g. buried-water exchange, minor side-chain rotamer transitions on >100 ns timescales) are not sampled.
- **Starting-structure bias**: initiated from the crystal structure; crystal-packing-stabilized conformations relax in solution (the small early RMSD rise then settling reflects this), but the trajectory does not explore alternative basins.
- **Apo, fresh solvent**: crystallographic buried waters and phosphate buffer were discarded; specific buried-water positions (a known feature of BPTI) were not seeded and would need longer equilibration or explicit placement to reproduce.
- **ff19SB/OPC** is appropriate for a folded globular protein stability run; it is not tuned for unfolding thermodynamics or disordered states (not relevant here).

## 9. Comparison to Literature
pubmed searched via mcp__pubmed (Step 2b and compare_to_literature). BPTI is a canonical MD reference;
no single paper reports an identical ff19SB/OPC 100 ns backbone-RMSD-vs-5PTI number, but the qualitative
benchmark (folded BPTI stays within ~1–2 Å backbone RMSD of crystal) is universally established.

| Our value | Published context | Source | Agreement |
|-----------|-------------------|--------|-----------|
| Backbone RMSD 1.06 Å (stable fold over 100 ns) | BPTI used as a small reference protein whose fold is stable in atomistic MD; 24 µs all-atom MD shows the 3-disulfide domain retains compactness | Elmaci et al. 2025, PMID:39978303, DOI:10.1016/j.redox.2025.103534 | ✓ qualitative |
| Compact, stable fold (Rg 11.1 Å) | BPTI 3D-hydration MD: well-defined hydration layer; buried waters match X-ray — implies a stable native structure | Kruchinin et al. 2022, PMID:36499117, DOI:10.3390/ijms232314785 | ✓ qualitative |
| Disulfides rigidify the core (low core RMSF) | SS bonds are critical to BPTI structural stability (multiscale QM/MM folding study) | Wesołowski et al. 2024, PMID:38512062, DOI:10.1021/acs.jpcb.4c00104 | ✓ qualitative |

No directly comparable published numerical backbone-RMSD value for the exact ff19SB/OPC/5PTI setup was found; numbers above are qualitative agreement only (no fabricated values).

## 10. Data Files
- Trajectory: simulations/prod/prod.nc (2000 frames, 50 ps interval, 100 ns)
- Production log: simulations/prod/prod.mdout
- Analysis: analysis/rmsd_backbone.dat, analysis/rmsf_byres.dat, analysis/radgyr.dat
- Plots: analysis/rmsd_backbone.png, analysis/rmsf_byres.png
- System: system/system.prmtop, system/system.inpcrd, system/protein_final.pdb
- Reports: PROCESS_REPORT.md (engineering log), PLAN.md (approved plan)

## 11. References

### Method references (methods actually used)
- ff19SB: Tian et al. 2020, J. Chem. Theory Comput. 16:528. PMID:31714766
- OPC water: Izadi, Anandakrishnan, Onufriev 2014, J. Phys. Chem. Lett. 5:3863. DOI:10.1021/jz501780a
- Joung–Cheatham / Li–Merz monovalent ions (OPC set): Joung & Cheatham 2008. PMID:18593145
- pmemd.cuda GPU MD: Salomon-Ferrer et al. 2013, J. Chem. Theory Comput. 9:3878. PMID:26592383
- cpptraj: Roe & Cheatham 2013, J. Chem. Theory Comput. 9:3084. PMID:26583988
- Amber 24 Reference Manual: §3 (force fields, p.33–34, 52), §13.6.5 (ions, p.249), §13.6.42 (solvateOct, p.263), §21.6 (MD/min params, p.386, 395) — consulted via RAG (Step 2a)

### System-specific literature (pubmed search)
- Kruchinin SE, Kislinskaya EE, Chuev GN, Fedotova MV. Protein 3D Hydration: A Case of Bovine Pancreatic Trypsin Inhibitor. Int J Mol Sci 2022. PMID:36499117, DOI:10.3390/ijms232314785
- Nobili G et al. Probing protein stability: towards a computational atomistic, reliable, affordable, and improvable model. Front Mol Biosci 2023. PMID:37325476, DOI:10.3389/fmolb.2023.1122269
- Wesołowski PA, Wales DJ, Pracht P. Multilevel Framework for Analysis of Protein Folding Involving Disulfide Bond Formation. J Phys Chem B 2024. PMID:38512062, DOI:10.1021/acs.jpcb.4c00104
- Elmaci DN et al. The structural integrity of human TFF1 under reducing conditions (BPTI as 3-disulfide reference, 24 µs MD). Redox Biol 2025. PMID:39978303, DOI:10.1016/j.redox.2025.103534

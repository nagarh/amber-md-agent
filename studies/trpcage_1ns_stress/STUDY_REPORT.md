# Study Report — Trp-cage (1L2Y) 1 ns Stability Stress Test
Date: 2026-05-17

## 1. Objective
Stress test of the amber-md-agent pipeline using Trp-cage miniprotein (1L2Y) as a well-characterized benchmark system. The goal is to verify that the full pipeline (system prep → minimization → heating → equilibration → 1 ns production → analysis) runs without errors and produces physically reasonable results. This is a stability check, not a folding or binding study.

## 2. System
- PDB: 1L2Y (Trp-cage, NMR, 20 conformers; model 1 used)
- Chains kept: A
- Construct: 20-residue miniprotein (NLYIQWLKDGGPSSGRPPPS)
- Atom count: 8471 (304 protein + 8166 TIP3P waters + 1 Cl⁻)
- Box: TIP3P, 12 Å padding, 52.7×50.4×43.6 Å orthogonal, volume 85,425 Å³
- Ligand: none
- Special features: none (no disulfides, no modified residues, full-length termini)

## 3. Protonation Rationale
Standard protonation at pH 7. All residues in default state.
| Residue | State | pKa context | Rationale |
|---------|-------|-------------|-----------|
| ASP9 | ASP (deprotonated) | pKa ~3.9 | Fully deprotonated at pH 7 |
| LYS8 | LYS+ (protonated) | pKa ~10.5 | Fully protonated at pH 7 |
| ARG16 | ARG+ (protonated) | pKa ~12.5 | Fully protonated at pH 7 |

Net charge: +2 (LYS8 + ARG16 - ASP9). Neutralized with 1 Cl⁻ ion.

## 4. Methods (mdin settings — actual values used)
| Step | Ensemble | Thermostat | Barostat | dt | cut | SHAKE | Restraints | Length |
|------|----------|------------|----------|-----|-----|-------|------------|--------|
| Min1 | NVT | — | — | — | 10 Å | — | 10 kcal/mol·Å² backbone | 5000 cyc |
| Min2 | NVT | — | — | — | 10 Å | — | none | 10000 cyc |
| Heat | NVT | Langevin γ=2 | — | 2 fs | 10 Å | H | 5 kcal/mol·Å² backbone | 100 ps, 0→300 K |
| Burst | NPT | Langevin γ=1 | Berendsen taup=0.5 | 2 fs | 10 Å | H | none | 3×10 ps |
| Equil2 | NPT | Langevin γ=2 | Berendsen taup=2.0 | 2 fs | 10 Å | H | 0.5 kcal/mol·Å² backbone | 250 ps |
| Prod | NPT | Langevin γ=2 | MC taup=5.0 | 2 fs | 10 Å | H | none | 1 ns (500,000 steps) |

## 5. Results
| Observable | Mean ± std | Range | Source |
|------------|------------|-------|--------|
| Backbone RMSD | 0.77 ± 0.17 Å | 0.0–~1.4 Å | analysis/rmsd.dat |
| RMSF N-term (Res 1) | 1.04 Å | — | analysis/rmsf.dat |
| RMSF C-term (Res 20) | 1.21 Å | — | analysis/rmsf.dat |
| RMSF core (Res 7, min) | 0.37 Å | — | analysis/rmsf.dat |
| Density | 0.9962 g/cc | 0.983–1.009 | prod.mdout AVERAGES |
| Temperature | 300.01 ± 3.25 K | — | prod.mdout AVERAGES |
| Etot | -21497 ± 97 kcal/mol | — | prod.mdout AVERAGES |
| MC barostat acceptance | 32.6% | — | prod.mdout footer |

Plots: analysis/rmsd_plot.png, analysis/rmsf_plot.png

## 6. Convergence Assessment
| Observable | drift_abs | threshold | status |
|------------|-----------|-----------|--------|
| Backbone RMSD | 0.043 Å | 0.5 Å | converged |

First-half mean RMSD: 0.789 Å. Second-half: 0.745 Å. Drift 0.043 Å (5.7%) — stable, no trend.

## 7. Key Findings
- Trp-cage remains stable throughout 1 ns: backbone RMSD 0.77 ± 0.17 Å (analysis/rmsd.dat), no drift (§6).
- Terminal residues (ASN1 = 1.04 Å, SER20 = 1.21 Å) most mobile; core (LEU7 = 0.37 Å) rigid — consistent with known Trp-cage topology.
- Density and temperature converged to expected values (0.9962 g/cc, 300.01 K) confirming correct NPT ensemble behavior.
- Full pipeline (tLEaP → min → heat → equil → 1ns prod → analysis) completed without errors in ~5 min wall time at 627 ns/day.

## 8. Caveats & Limitations
- 1 ns far below folding/unfolding timescale for Trp-cage (µs); this is a stability check only, not a folding study.
- Single replicate; no enhanced sampling; no replica exchange.
- TIP3P water model overestimates diffusion vs experiment; ff14SB+TIP3P is well-validated for folded proteins but ff19SB+OPC would give better IDP/unfolding sampling.
- Starting structure is from NMR model 1 — crystal contacts absent but NMR ensemble bias present.
- validate_step tool reads final-frame temperature (290 K) instead of AVERAGES block (300.01 K) — false WARN documented in PROCESS_REPORT.md §Bugs.

## 9. Comparison to Literature
| Our value | Published value | Source (PMID, DOI) | Agreement |
|-----------|-----------------|---------------------|-----------|
| Backbone RMSD 0.77 ± 0.17 Å | ~1–2 Å for Trp-cage MD (implicit solvent, various FF) | Heilmann et al. 2020, PMID:33097750, DOI:10.1038/s41598-020-75239-7 | Consistent (our explicit TIP3P slightly lower RMSD — expected for folded state) |
| Density 0.9962 g/cc | ~0.99–1.00 g/cc (TIP3P/ff14SB standard) | No directly comparable Trp-cage TIP3P/ff14SB paper found | Consistent with TIP3P expected density |

No directly comparable explicit TIP3P/ff14SB 1ns Trp-cage RMSD found in literature — Heilmann 2020 uses implicit solvent and MC, not comparable in detail. Value of 0.77 Å is physically reasonable for stable folded miniprotein.

## 10. Data Files
- Trajectory: simulations/prod/prod.nc (500 frames, 2 ps/frame)
- Stripped trajectory: analysis/prod_stripped.nc (1.85 MB)
- RMSD: analysis/rmsd.dat | Plot: analysis/rmsd_plot.png
- RMSF: analysis/rmsf.dat | Plot: analysis/rmsf_plot.png
- Engineering log: PROCESS_REPORT.md
- Approved plan: PLAN.md

## 11. References

### Method references
- ff14SB: Maier et al. 2015. PMID:26574453. DOI:10.1021/acs.jctc.5b00255
- TIP3P: Jorgensen et al. 1983. DOI:10.1063/1.445869
- Joung-Cheatham ions: Joung & Cheatham 2008. PMID:18593145
- Amber manual: Amber24.pdf — sections consulted: §3.1 (ff14SB), §13.7 (tLEaP solvation), §21.6 (thermostat/barostat), §22.6 (GPU tips), §36.11 (cpptraj RMSD/RMSF)
- cpptraj: Roe & Cheatham 2013. DOI:10.1021/ct400341p

### System-specific literature (from pubmed_server search)
- Heilmann N et al. 2020. "Sampling of the conformational landscape of small proteins with Monte Carlo methods." Sci Rep. PMID:33097750. DOI:10.1038/s41598-020-75239-7
- Hao GF et al. 2015. "Multiple Simulated Annealing-Molecular Dynamics (MSA-MD) for Conformational Space Search of Peptide and Miniprotein." Sci Rep. PMID:26492886. DOI:10.1038/srep15568

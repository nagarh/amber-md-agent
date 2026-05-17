# Study Report — Apo HIV-1 Protease (PDB 1HHP) at pH 5.5
Date: 2026-05-15

## Objective
Smoke-test 1 ns MD of apo HIV-1 protease at pH 5.5 to characterize flap
dynamics with protonation states relevant to inhibitor-binding studies.

## System
- PDB: 1HHP, biological dimer (chains A + B, 99 res each, 198 total)
- Asymmetric unit only contained chain A — BIOMT op 2 (REMARK 350) applied
  to generate chain B → full biological dimer (1516 protein atoms)
- Apo (no ligand)
- Total atom count: 31,296 (protein + 9386 TIP3P waters + neutralizing Na+/Cl-)
- Box: 12 Å TIP3P padding
- FF: ff14SB (protein), TIP3P (water), Joung-Cheatham (ions)

## Protonation rationale (pH 5.5)
- Catalytic dyad: ASP25(A) protonated → ASH; ASP25(B) deprotonated → ASP.
  Mono-protonated state is the accepted physiological model for apo
  HIV-1 PR and for most inhibitor-bound complexes near experimental
  pH (5–6) — supported by NMR + computational studies.
- HIS69 (both chains): HIP. Only His in protein, solvent-exposed.
  pH 5.5 < typical His pKa (~6.0) → fully protonated.
- All other Asp/Glu: standard ionized (ASP/GLU).

## Methods
- Min1: 5000 cycles (2500 SD + 2500 CG), restraint_wt=10 kcal/mol·Å² on solute
- Min2: 10000 cycles full minimization, no restraints
- Heat: NVT 100 ps, 0→300 K Langevin γ=2.0, restraints 5 kcal/mol·Å² on solute
- Burst density: pmemd.cuda 10 ps bursts, barostat=1, taup=0.5, no restraints
  → converged in 2 iterations (mean 1.0108 g/cc, fluct 0.0033 g/cc)
- Equil2: 500 ps NPT re-equilibration, barostat=1 taup=2.0, restraint_wt=0.5
  on solute (warms back from burst cooldown)
- Production: 1 ns NPT, MC barostat taup=5.0, no restraints, dt=2 fs, SHAKE H

## Results
| Metric | Mean | Range | Convergence (drift_abs) |
|--------|------|-------|--------------------------|
| Backbone RMSD | 1.09 Å | — | 0.247 Å (converged) |
| Flap tip distance (Ile50–Ile50' Cα) | 5.60 Å | 4.05–7.30 Å | 0.55 Å |
| Catalytic dyad distance (ASH25-ASP25' OD) | 3.39 Å | 2.59–3.67 Å | (stable) |
| Flap region mean RMSF | 0.94 Å | max 2.10 Å | — |
| Final density | 1.013 g/cc | — | fluct 0.005 g/cc |
| Final temperature | 290.2 K | — | (10 K below target) |

## Key Findings
1. **Closed flap conformation throughout 1 ns** — flap tip distance 5.6 Å
   matches closed-state crystal geometry (4–7 Å). No opening event observed.
2. **Catalytic dyad H-bond maintained** — ASP25(ASH)-ASP25'(ASP) carboxyl
   distance ~3.4 Å throughout, consistent with mono-protonated bridge.
3. **Flap region most flexible** — RMSF max 2.1 Å at flap tip residues,
   compared to ~0.5–1.0 Å in core β-sheet. Expected for HIV-1 PR.

## Caveats — critical for interpretation
- **1 ns is NOT sufficient for true flap dynamics.** Flap opening events
  occur on 10–100 ns timescales (Hornak & Simmerling, PNAS 2006). 1 ns
  captures only equilibrium fluctuations in the closed state.
- Temperature ran ~10 K below target (290 K vs 300 K) — system inherited
  cold state from density burst. For publication-quality study, extend
  equil2 to 1 ns or use velocity rescaling before production.
- No ligand bound → flaps would be MORE mobile than holo HIV-1 PR.
  1 ns insufficient to capture this.

## Data Files
- Trajectory: simulations/prod/prod.nc (1 ns, 200 frames @ 5 ps)
- Stripped (no water): analysis/prod_stripped.nc
- RMSD: analysis/rmsd_backbone.dat
- RMSF: analysis/rmsf_per_residue.dat, analysis/rmsf_flaps.dat
- Flap tip distance: analysis/flap_tip_distance.dat
- Active site distance: analysis/active_site.dat
- Process log: PROCESS_REPORT.md

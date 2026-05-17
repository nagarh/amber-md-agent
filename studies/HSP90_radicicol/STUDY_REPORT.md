# Simulation Report — HSP90_radicicol
Date: 2026-05-14

## Objective
Characterize binding of natural product radicicol (RDC) to HSP90-alpha N-terminal ATPase domain (PDB: 4EGK) via MD simulation and MM-GBSA, and compare computed ΔG against experimental Kd.

## System
| Property | Value |
|----------|-------|
| Protein | HSP90-alpha NTD (PDB: 4EGK, 1.69 Å, clashscore 2.96) |
| Ligand | Radicicol RDC (CID: 6323491, C18H17ClO6, charge 0) |
| Total atoms | 42,058 |
| Box | TIP3P, 12 Å padding, 0.15 M NaCl |
| Simulation length | 200 ps production (test run) |

## Methods
| Parameter | Value |
|-----------|-------|
| Protein FF | ff14SB |
| Ligand FF | GAFF2 (AM1-BCC charges) |
| Water | TIP3P |
| Thermostat | Langevin, γ=1.0 ps⁻¹, 300 K |
| Barostat | Berendsen (equil), MC barostat=2 (prod) |
| Timestep | 2 fs |
| PME cutoff | 10.0 Å |
| SHAKE | ntc=2, ntf=2 |
| MM-GBSA | igb=5, saltcon=0.150, 20 frames, 1-trajectory |

## Results

### MD Quality Notes
- Heat: NSTEP=500000, T=285.8 K (NVT) — PASS
- Density convergence: 0.818 → 1.006 g/cc via 4-restart burst loop
- Production: density 1.021 g/cc — PASS; avg temp 239.6 K (below 300 K target — density bursts chilled system, insufficient re-equilibration in 200 ps)

### MM-GBSA Energy Breakdown (ΔComplex − ΔReceptor − ΔLigand)
| Component | ΔG (kcal/mol) | Std.Dev |
|-----------|--------------|---------|
| ΔvdW | -38.37 | 2.26 |
| ΔEEL | -60.77 | 4.76 |
| ΔEGB (solvation) | +62.76 | 2.91 |
| ΔESURF | -5.45 | 0.08 |
| **ΔG_total** | **-41.83** | **2.39** |

### Binding Free Energy Comparison
| Method | ΔG (kcal/mol) | Notes |
|--------|--------------|-------|
| MM-GBSA (this study) | -41.83 ± 2.39 | No entropy correction, 200 ps |
| Experimental (Kd=1.2 nM, HSP90α) | -12.24 | ChEMBL 2019 |
| Experimental (Kd=4.2 nM, HSP90α) | -11.50 | ChEMBL 2013 |
| Experimental (Kd=19 nM, HSP90) | -10.60 | ChEMBL 2009 |

**Deviation: -41.83 vs -10.6 to -12.2 kcal/mol → overestimate by ~29–31 kcal/mol**

## Key Findings

1. **MM-GBSA grossly overestimates binding** by ~30 kcal/mol. Primary causes:
   - No entropy correction (-TΔS): conformational entropy loss on binding typically +15–25 kcal/mol — omitting it inflates |ΔG| significantly
   - Very poor sampling: 20 frames from 200 ps → high variance; true MM-GBSA requires 500–1000 frames from ≥10 ns equilibrated trajectory
   - System temperature 239.6 K (not 300 K) — density burst convergence protocol chilled the system; under-temperature inflates electrostatic terms

2. **Dominant binding terms**: vdW (-38.4) and electrostatics (-60.8) both strongly favorable; polar solvation penalty (+62.8) partially cancels. Net gas-phase ΔG = -99.1 kcal/mol, partially offset by solvation.

3. **For publication-quality results** this system requires:
   - ≥100 ns equilibrated production at correct 300 K
   - Entropy correction via nmode or quasi-harmonic approximation
   - Or replace MM-GBSA with FEP/TI for absolute ΔG

## Data Files
- Topology: system/system.prmtop
- Trajectory: simulations/prod/prod.nc (200 ps)
- MM-GBSA input: analysis/mmgbsa.in
- MM-GBSA results: analysis/mmgbsa_results.dat
- Process log: PROCESS_REPORT.md

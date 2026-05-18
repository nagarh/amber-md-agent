# Plan — trpcage_remd_folding
Date: 2026-05-17

## Objective
Characterize the folding/unfolding thermodynamics of the Trp-cage miniprotein (1L2Y)
across 270–600 K using temperature REMD. Quantify Tm, ΔG(T), folding pathways, and
the conformational free-energy landscape at physiological temperature.

## System (reused from trpcage_1ns_stress — fully validated)
- PDB: 1L2Y, monomeric (chain A, 20 residues)
- Atom count: 8471 (304 protein + 8166 TIP3P waters + 1 Cl⁻)
- Box: TIP3P, 12 Å padding, 52.7×50.4×43.6 Å orthogonal
- prmtop: studies/trpcage_1ns_stress/system/system.prmtop
- Starting rst7: studies/trpcage_1ns_stress/simulations/equil/equil2.rst7 (300K NPT equilibrated)
- Special features: none (no disulfides, no modified residues, full-length termini)

## Force fields
| Component | FF | Reason |
|-----------|----|--------|
| Protein | ff14SB | Validated for small structured proteins; same as stress test |
| Water | TIP3P | Standard for ff14SB; validated in stress test |
| Ions | Joung-Cheatham | Matches TIP3P |

## Protonation states (at pH 7.0)
Same as trpcage_1ns_stress — all standard. Net charge +2, neutralized by 1 Cl⁻.
| Residue | State | Rationale |
|---------|-------|-----------|
| ASP9 | ASP (deprotonated) | pKa ~3.9 |
| LYS8 | LYS+ (protonated) | pKa ~10.5 |
| ARG16 | ARG+ (protonated) | pKa ~12.5 |

## REMD Temperature Ladder
16 replicas (cluster courtesy limit), geometric spacing, ratio ≈ 1.0547 (~5.5% per step).
Target exchange rate: 15–25% (slightly wider spacing than 24-replica design; acceptable for
this small system where energy fluctuations are large relative to ΔU between replicas).
Tm region (315–320 K) bracketed by T02=300.4 K and T03=316.8 K.

| Replica | T (K) | Replica | T (K) |
|---------|-------|---------|-------|
| 00 | 270.0 | 08 | 413.4 |
| 01 | 284.8 | 09 | 436.0 |
| 02 | 300.4 | 10 | 459.8 |
| 03 | 316.8 | 11 | 484.9 |
| 04 | 334.1 | 12 | 511.4 |
| 05 | 352.3 | 13 | 539.4 |
| 06 | 371.6 | 14 | 568.9 |
| 07 | 392.0 | 15 | 600.0 |

## Simulation Protocol

### Phase 1 — Pre-equilibration (24 independent NVT runs)
| Step | Setting | Time | Source |
|------|---------|------|--------|
| NVT pre-equil | Langevin γ=2, each replica at target T, no restraints | 100 ps | skill/literature |

- Start: equil2.rst7 (NPT-equilibrated 300K)
- Each replica thermalizes independently at its target T
- Output: preq_{00..23}.rst7 → input for REMD production
- Submitted as SLURM array job (24 tasks, 1 GPU each or 4 CPUs each)

### Phase 2 — REMD Production
| Parameter | Value | Source |
|-----------|-------|--------|
| Ensemble | NVT (ntp=0, ntb=1) | standard T-REMD requirement |
| Thermostat | Langevin γ=2 | English 2014 |
| Exchange interval | 1 ps (nstlim=500, dt=0.002) | English 2014; Kasavajhala 2020 |
| Total exchanges | 100,000 per replica | DEFAULT |
| Production length | 100 ns per replica | DEFAULT |
| Aggregate MD | 1.6 µs (16 × 100 ns) | — |
| ntwx | 5000 steps (10 ps/frame) | → 10,000 frames/replica |
| ntpr | 500 steps (1 ps log output) | — |
| ntwr | 50,000 steps (100 ps restart) | — |
| cut | 10.0 Å | consistent with stress test |
| SHAKE | hydrogen bonds | dt=2 fs |
| Engine | pmemd.cuda.MPI (GPU, primary) | — |
| Fallback | pmemd.MPI (CPU, 4 cores/replica) | if <16 GPUs unavailable |

### REMD mdin (per replica — only temp0/tempi differ)
```fortran
Trp-cage T-REMD replica
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=500,
  dt=0.002,
  temp0=<Ti>, tempi=<Ti>,
  ntt=3, gamma_ln=2.0,
  ntb=1, ntp=0,
  cut=10.0,
  ntwe=0, ntwx=5000, ntwr=50000, ntpr=500,
  numexchg=100000,
  ioutfm=1,
 /
```

### REMD run command
```bash
mpirun -np 16 pmemd.cuda.MPI -ng 16 \
  -groupfile remd_group.in \
  -rem 1 -remlog remd.log
```
CPU fallback: replace `pmemd.cuda.MPI` with `pmemd.MPI` and adjust `-np 64` (4 cores/replica).

## Box
- Solvent: TIP3P, 12 Å padding (reuse stress-test box)
- Ions: 1 Cl⁻ (neutralize +2 net charge)

## Analysis Targets
1. Exchange acceptance rate per replica pair (from rem.log)
2. Replica round-trips (T-space diffusion → convergence indicator)
3. Backbone RMSD to NMR structure vs T → folded vs unfolded fraction
4. Q (fraction native contacts) vs T → sigmoid midpoint = Tm
5. Cv(T) from ⟨δE²⟩/kT² → secondary Tm estimate
6. Free energy F(RMSD) per temperature window
7. 2D FEL at 300 K: RMSD vs Rg
8. Folding pathway characterization at T = 285, 315, 325 K (three regimes from Andryushchenko 2017)
9. Compare computed Tm to experiment: ~315–320 K (Neidigh 2002)

## Literature Precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable |
|------------------------|--------|------------|----|----------------|
| English & García 2014, PMID:24448113, DOI:10.1039/c3cp54339k | Trp-cage TC10b REMD | 1 µs/replica | Not ff14SB | Tm, ΔG(P,T), 2-state folding |
| Hatch et al. 2014, PMID:24559466, DOI:10.1021/jp410651u | Trp-cage REMD | Extended | REMD | Phase diagram, negative pressure |
| Kim et al. 2016, PMID:27457961, DOI:10.1073/pnas.1607500113 | Trp-cage cold denat. | Atomistic | TIP4P/2005 | Cold denat. at 210 K; helix survives |
| Andryushchenko & Chekmarev 2017, PMID:28983809, DOI:10.1007/s10867-017-9470-7 | Trp-cage folding pathways | MD | various | Pathway switch at Tm=315 K |
| Chan et al. 2023, PMID:36705525, DOI:10.1021/acs.jpclett.2c03680 | Trp-cage unfolding (SAXS+MD) | µs | — | Intermediate at 1 µs, full unfold at 5 µs |

## Method Best Practices (Step 2c — REMD keyword triggered)
Triggered by: `REMD` (user prompt)

| Paper (PMID, year) | Recommendation | Amber flag | Adopted? |
|---------------------|----------------|------------|----------|
| Kasavajhala 2020, PMID:33142060 | GPU REMD (pmemd.cuda.MPI) 20× faster than CPU for RREMD | pmemd.cuda.MPI | ✓ |
| Kasavajhala 2020, PMID:33142060 | NVT ensemble for T-REMD | ntp=0, ntb=1 | ✓ |
| English 2014, PMID:24448113 | 1 µs/replica for rigorous Trp-cage thermodynamics | numexchg=1e6 if feasible | 100 ns (default — see caveats) |
| English 2014, PMID:24448113 | Exchange every 1-2 ps | nstlim=500-1000 | ✓ nstlim=500 |
| Grossfield 2018, PMID:30533602 | Track replica round-trips for convergence | rem.log analysis | ✓ |

### Deviations from defaults
| Default | Adopted | Reason |
|---------|---------|--------|
| NPT production | NVT for REMD | T-REMD requires NVT; NPT REMD has volume-coupling complications |
| Single replicate | 24 replicas | REMD by design |
| Standard MD | pmemd.cuda.MPI with -rem 1 | T-REMD requires groupfile + -rem flag |
| 100 ns/replica | (English 2014 used 1 µs) | Trp-cage is 20 residues; 100 ns at high T (>400K) samples many fold/unfold cycles. Extend if Tm does not converge. |

## Walltime Estimates
| Engine | ns/day per replica | 100 ns wall time | SLURM nodes |
|--------|-------------------|------------------|-------------|
| pmemd.cuda.MPI (GPU) | ~600 ns/day | ~4 hr (all 16 parallel) | 16 nodes × 1 GPU |
| pmemd.MPI (CPU, 4 cores/replica) | ~15 ns/day | ~7 days | 1 node × 64 CPUs |

Primary: GPU (16 nodes, within cluster courtesy limit). Request 12 hr walltime (3× safety).
CPU fallback: 168 hr max walltime.
Pre-equil array: 16 × 100 ps → ~5 min each on GPU. Walltime 00:30:00.

## File Map
```
studies/trpcage_remd_folding/
├── system/                    ← symlinks to stress-test prmtop/rst7
├── simulations/
│   ├── pre_equil/             ← preq_00.mdin .. preq_23.mdin, preq_??.rst7
│   └── remd_prod/             ← remd_??.mdin, remd_group.in, remd_??.nc, rem.log
├── analysis/
│   ├── by_temp/               ← rmsd_<T>.dat, q_<T>.dat per temperature
│   ├── demux/                 ← demuxed sorted-by-T trajectories
│   └── plots/                 ← Cv(T).png, P_fold(T).png, FEL_300K.png
└── logs/                      ← SLURM .out/.err
```

## Caveats / Limitations
- 100 ns/replica < 1 µs used by English & García 2014 for rigorous TC10b thermodynamics. Tm estimate will be approximate; extend to 200–500 ns if needed.
- ff14SB+TIP3P: known to overestimate alpha-helix stability slightly vs TIP4P-Ew or OPC. Cold denaturation (below ~280 K) predictions less reliable with TIP3P (Kim 2016 uses TIP4P/2005).
- GPU REMD requires 24 simultaneous GPU nodes — queue time may be long. CPU fallback available.
- pmemd REMD trajectories are sorted by replica index, not temperature. Demux required before per-temperature analysis.
- T range extends to 600 K — TIP3P water at 600 K is well above boiling point and unphysical for protein hydration. High-T replicas (~500–600 K) serve as unfolded-state reservoir only; thermodynamic analysis restricted to 270–420 K.

## Approval: APPROVED 2026-05-17 (16 replicas, cluster courtesy limit)

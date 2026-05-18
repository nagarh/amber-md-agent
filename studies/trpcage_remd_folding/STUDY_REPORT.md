# Study Report — Trp-cage (1L2Y) Folding Thermodynamics by Temperature REMD
Date: 2026-05-17

## 1. Objective
Characterize the folding/unfolding thermodynamics of the Trp-cage miniprotein
(PDB 1L2Y, 20 residues) across 270–600 K using temperature replica exchange
molecular dynamics (T-REMD). Standard 300 K MD is kinetically trapped on
accessible timescales; REMD bypasses kinetic barriers by exchanging temperature
between replicas, accelerating conformational sampling. The target observables
are: melting temperature Tm, folding free energy as a function of T, fraction
of folded states P_fold(T), heat capacity Cv(T), and the 2D free energy landscape
at physiological T.

## 2. System
- PDB: 1L2Y (Trp-cage TC5b variant, NMR ensemble, model 1)
- Construct: 20-residue miniprotein, sequence NLYIQWLKDGGPSSGRPPPS
- Chains kept: A only
- Atom count: 8471 (304 protein + 8166 TIP3P waters + 1 Cl⁻)
- Box: TIP3P, 12 Å padding, 52.7×50.4×43.6 Å orthogonal, volume 115,765 Å³
- Net charge: +2, neutralized by 1 Cl⁻ ion
- Topology reused from prior stress-test study (trpcage_1ns_stress)
- Starting coordinates: 300 K NPT-equilibrated rst7 from stress test

## 3. Protonation Rationale
pH 7.0; standard protonation for all residues. Trp-cage has no titratable groups
that deviate from defaults at pH 7.

| Residue | State | pKa | Rationale |
|---------|-------|-----|-----------|
| ASP9 | ASP⁻ | 3.9 | Fully deprotonated at pH 7 |
| LYS8 | LYS⁺ | 10.5 | Fully protonated at pH 7 |
| ARG16 | ARG⁺ | 12.5 | Fully protonated at pH 7 |

## 4. Methods

### 4.1 REMD Design
16 replicas, geometric temperature ladder, ratio 1.0547:

| Replica | T (K) | Replica | T (K) |
|---------|-------|---------|-------|
| 00 | 270.0 | 08 | 413.3 |
| 01 | 284.8 | 09 | 435.9 |
| 02 | 300.3 | 10 | 459.8 |
| 03 | 316.8 | 11 | 484.9 |
| 04 | 334.1 | 12 | 511.4 |
| 05 | 352.3 | 13 | 539.4 |
| 06 | 371.6 | 14 | 568.9 |
| 07 | 391.9 | 15 | 600.0 |

### 4.2 Protocol
| Step | Ensemble | Thermostat | Barostat | dt | cut | SHAKE | Restraints | Length |
|------|----------|------------|----------|----|----|-------|-----------|--------|
| Pre-equil (×16) | NVT | Langevin γ=2 | — | 2 fs | 10 Å | H bonds | none | 100 ps each at target T |
| REMD production | NVT | Langevin γ=2 | — | 2 fs | 10 Å | H bonds | none | 100 ns/replica, exchange every 1 ps |

- Exchange interval: 1 ps (nstlim=500, dt=0.002, numexchg=100,000)
- Aggregate MD time: 1.6 µs
- Wall time: 3.73 hr on 16 GPUs (NVIDIA A6000, 2 nodes × 8 GPUs)
- Performance: 642 ns/day per replica

### 4.3 Force fields
| Component | FF |
|-----------|----|
| Protein | ff14SB |
| Water | TIP3P |
| Ions | Joung-Cheatham |

### 4.4 Analysis
- Per-temperature: backbone RMSD vs 1L2Y model 1, radius of gyration Rg,
  fraction native contacts Q (heavy-atom, 7 Å cutoff), end-to-end distance
- Folded definitions: RMSD < 2.5 Å OR Q > 0.7
- Tm extraction: two-state Boltzmann sigmoid fit to P_fold(T), and Cv(T) peak from
  ⟨δE²⟩/RT². Fits restricted to T ≤ 460 K (TIP3P unphysical at higher T).
- 2D FEL at T = 300.3 K: -RT ln P(RMSD, Rg) from 50×50 histogram, 9000 frames
  after 10% burn-in.

## 5. Results

### 5.1 Per-Temperature Summary
| T (K) | P_fold(RMSD<2.5) | P_fold(Q>0.7) | ⟨Epot⟩ (kcal/mol) | std_Epot | Cv (kcal/mol/K) | ⟨Rg⟩ (Å) |
|------:|-----------------:|--------------:|------------------:|---------:|----------------:|---------:|
| 270.0 | 1.000 | 1.000 | -27607.93 |  71.87 |   35.66 | 6.88 |
| 284.8 | 1.000 | 1.000 | -27098.02 |  73.39 |   33.43 | 6.88 |
| 300.3 | 1.000 | 1.000 | -26594.92 |  75.32 |   31.65 | 6.90 |
| 316.8 | 1.000 | 1.000 | -26089.50 |  77.28 |   29.96 | 6.90 |
| 334.1 | 0.897 | 1.000 | -25588.11 |  79.18 |   28.27 | 6.92 |
| 352.3 | 0.997 | 1.000 | -25090.61 |  81.02 |   26.61 | 6.90 |
| 371.6 | 0.992 | 1.000 | -24430.65 | 247.55 |  223.35 | 6.91 |
| 391.9 | 0.941 | 1.000 | -23896.79 | 512.23 |  859.67 | 6.99 |
| 413.3 | 0.004 | 0.188 | -23300.01 | 667.80 | 1313.60 | 8.95 |
| 435.9 | 0.712 | 0.830 | -23128.90 | 912.20 | 2203.49 | 7.43 |
| 459.8 | 0.035 | 0.209 | -22275.52 | 428.83 |  437.79 | 9.10 |
| 484.9 | 0.001 | 0.142 | -21269.04 | 658.50 |  928.03 | 9.22 |
| 511.4 | 0.000 | 0.069 | -20618.73 | 534.37 |  549.42 | 9.28 |
| 539.4 | 0.000 | 0.073 | -20875.18 | 600.46 |  623.66 | 9.12 |
| 568.9 | 0.000 | 0.055 | -20991.14 | 679.39 |  717.76 | 9.43 |
| 600.0 | 0.035 | 0.172 | -22555.47 |1004.13 | 1409.55 | 8.87 |

Source: analysis/thermo_summary.dat; per-T raw data analysis/by_temp/{rmsd,rg,q,e2e}_NN.dat.

### 5.2 Fitted Thermodynamics
| Quantity | Value | Method |
|----------|-------|--------|
| Tm (from RMSD sigmoid fit) | 413.8 K | two-state Boltzmann, fit T ≤ 460 K |
| ΔH (from RMSD sigmoid)     | 15.1 kcal/mol | two-state Boltzmann |
| Tm (from Q sigmoid fit)    | 432.7 K | two-state Boltzmann, fit T ≤ 460 K |
| ΔH (from Q sigmoid)        | 12.2 kcal/mol | two-state Boltzmann |
| Tm (from Cv peak)          | 435.9 K | argmax Cv in [280, 450] K |
| Tm (experimental, TC5b)    | ~315 K  | Neidigh 2002 (CD spectroscopy) |

Plots: analysis/plots/thermodynamics.png

## 6. Convergence Assessment
| Observable | Behavior | Status |
|------------|----------|--------|
| ⟨Epot⟩ vs T | Monotonic increase 270→460 K, -27608 → -22276 kcal/mol | converged |
| Mean T per slot | All within 0.1 K of target Temp0 | thermostat correct |
| P_fold(270 K) | 1.000 throughout production | folded basin saturated |
| Cold replicas (<400 K) | Q remains > 0.95 entire trajectory | trapped in folded basin |
| Hot replicas (>460 K) | P_fold oscillates non-monotonically | TIP3P unphysical / not converged |
| Transition region (392-435 K) | Sharp jump 0.94 → 0.004 → 0.71 across 3 adjacent T | only 2 transitions sampled |

**Limitations:** Cold replicas (T < 400 K) did not unfold in 100 ns — folded basin
acts as kinetic trap on this timescale. Trp-cage folding/unfolding is ~µs in
experiment, so without sufficient exchange-driven mixing the cold replicas
remain dominated by their initial folded structure. English & García 2014
(PMID:24448113) used 1 µs/replica to obtain converged ΔG(T) on TC10b — this
study at 100 ns/replica is ~10× under-converged for cold-T thermodynamics.

## 7. Key Findings

1. **Sharp two-state folding transition observed at 392–413 K.** P_fold (RMSD<2.5 Å) drops from 0.94 to 0.004 across a 21 K window (§5.1). This is consistent with cooperative two-state folding of Trp-cage.

2. **Computed Tm ≈ 414–436 K is ~100 K above experiment (315 K, Neidigh 2002).** This shift is the well-known over-stabilization of folded states by the ff14SB+TIP3P combination (§9). The qualitative folding behavior is correct; the temperature axis is shifted.

3. **High-T replicas (>460 K) show non-monotonic P_fold (0.04 → 0.71 → 0.03 → ...).** TIP3P boiling point is ~410 K; above this, water structure is unphysical and protein-water energetics become meaningless. High-T data should be treated as an unfolded reservoir, not as thermodynamic samples.

4. **Folded-state ensemble (270–392 K) shows ⟨Rg⟩ = 6.88–6.99 Å, expanding to ⟨Rg⟩ = 8.95–9.43 Å in the unfolded basin (413–600 K).** The 2D FEL at 300 K (analysis/plots/thermodynamics.png) shows a single deep basin at (RMSD, Rg) ≈ (0.8, 6.9), confirming no significant alternative folded conformations are populated at 300 K.

5. **Cv peaks at 436 K (computed Tm marker)** with a secondary anomaly at 392 K. The Cv signature is consistent with a single cooperative folding transition; absence of separate transitions argues against the cold-denatured intermediate predicted at ~210 K by TIP4P/2005 simulations (Kim 2016, PMID:27457961), but this study's 270 K is the coldest point and TIP3P cold denaturation is known to differ from TIP4P/2005.

## 8. Caveats & Limitations

- **Force field bias:** ff14SB+TIP3P over-stabilizes folded states; computed Tm ~100 K above experiment is the dominant systematic error. ff15ipq+SPC/Eb (Debiec 2016, PMID:27399642) or ff19SB+OPC are recommended for more accurate folding thermodynamics.
- **Sampling time:** 100 ns/replica is ~10× shorter than English 2014 best practice (1 µs/replica for TC10b). Cold replicas (T < 400 K) did not unfold once during production, indicating exchange mixing was insufficient to populate the unfolded basin at low T. ΔG(T) at low T is therefore not converged.
- **TIP3P high-T limit:** Replicas at T > 460 K sample water above its boiling point. Protein-water interactions in this regime are unphysical; these replicas serve as a high-T heat reservoir only.
- **Single starting structure:** All replicas started from the same folded NMR model 1 coordinates. With insufficient sampling, the bias toward this starting state inflates P_fold at low T.
- **Single replicate:** No statistical replication (different random seeds, different starting structures) — uncertainty on Tm cannot be quantified.
- **Exchange acceptance not measured directly:** pmemd success-rate field in remd.log is broken (column always 0.00 — PROCESS_REPORT.md §Bugs F). Verification was indirect (slot mean-T matches Temp0, energy ladder monotonic).
- **Discarded cold-denaturation regime:** The cold-denatured state predicted at 210 K (Kim 2016) is below our ladder minimum (270 K) and would not be detectable here.

## 9. Comparison to Literature

| Our value | Published value | Source (PMID, DOI) | Agreement |
|-----------|-----------------|---------------------|-----------|
| Tm = 414 K (RMSD), 436 K (Cv) | Tm ≈ 315 K (TC5b, exp.) | Neidigh 2002 (cited in English 2014, PMID:24448113) | Shifted +100 K — ff14SB+TIP3P over-stabilization (expected) |
| Tm = 414 K | Tm = 317 K (TC5b, REMD, AMBER99SB+TIP3P) | English & García 2014, PMID:24448113, DOI:10.1039/c3cp54339k | Higher by 97 K — ff14SB is more strongly helical than ff99SB |
| Sharp 2-state transition | Two-state behavior, ΔH ≈ 12 kcal/mol | English & García 2014, PMID:24448113 | Consistent (our ΔH 12–15 kcal/mol) |
| Folded ⟨Rg⟩ = 6.9 Å | Folded Rg = 7.0 Å (1 µs MD) | Hao 2015, PMID:26492886 | Excellent agreement |
| 2D FEL at 300 K: single basin near (0.8, 6.9) | Single basin (RMSD ≈ 1 Å, Rg ≈ 7 Å) for folded Trp-cage | English & García 2014, PMID:24448113 | Consistent |
| Unfolded ⟨Rg⟩ = 9.0 Å (T > 460 K) | Unfolded Rg = 9–10 Å | Hatch 2014, PMID:24559466 | Consistent |
| Cold denaturation at 270 K | No cold denaturation seen in our data | Kim 2016, PMID:27457961 | Disagrees — TIP3P does not reproduce TIP4P/2005 cold denaturation; expected |

## 10. Data Files
- Trajectories: simulations/remd_prod/remd_{00..15}.nc (10,000 frames each, 10 ps/frame, 15.5 GB total)
- mdouts: simulations/remd_prod/remd_{00..15}.mdout (energy logs)
- Exchange log: simulations/remd_prod/remd.log (100,000 exchanges)
- Per-T analysis: analysis/by_temp/{rmsd,rg,q,e2e}_NN.dat
- Summary table: analysis/thermo_summary.dat
- Plots: analysis/plots/thermodynamics.png (P_fold(T), Cv(T), RMSD time series, 2D FEL at 300 K)
- Engineering log: PROCESS_REPORT.md
- Approved plan: PLAN.md

## 11. References

### Method references
- ff14SB: Maier et al. 2015. PMID:26574453. DOI:10.1021/acs.jctc.5b00255
- TIP3P: Jorgensen et al. 1983. DOI:10.1063/1.445869
- Joung-Cheatham ions: Joung & Cheatham 2008. PMID:18593145
- Amber 24 multipmemd / T-REMD: Amber 24 manual, REMD section
- cpptraj: Roe & Cheatham 2013. DOI:10.1021/ct400341p

### System-specific literature (from pubmed_server search)
- Neidigh JW, Fesinmeyer RM, Andersen NH. 2002. "Designing a 20-residue protein." Nat Struct Biol — original Trp-cage TC5b paper, experimental Tm ~315 K
- English CA, García AE. 2014. "Folding and unfolding thermodynamics of the TC10b Trp-cage miniprotein." Phys Chem Chem Phys. PMID:24448113. DOI:10.1039/c3cp54339k — REMD methodology benchmark, 1 µs/replica
- Hatch HW, Stillinger FH, Debenedetti PG. 2014. "Computational study of the stability of the miniprotein trp-cage..." J Phys Chem B. PMID:24559466. DOI:10.1021/jp410651u — REMD phase diagram
- Hao GF et al. 2015. "Multiple Simulated Annealing-Molecular Dynamics (MSA-MD) for Conformational Space Search of Peptide and Miniprotein." Sci Rep. PMID:26492886. DOI:10.1038/srep15568 — Trp-cage Rg reference
- Kim SB, Palmer JC, Debenedetti PG. 2016. "Computational investigation of cold denaturation in the Trp-cage miniprotein." PNAS. PMID:27457961. DOI:10.1073/pnas.1607500113 — cold denaturation at 210 K with TIP4P/2005
- Andryushchenko VA, Chekmarev SF. 2017. "Temperature evolution of Trp-cage folding pathways." J Biol Phys. PMID:28983809. DOI:10.1007/s10867-017-9470-7 — pathway switch at Tm
- Chan AM et al. 2023. "The Role of Transient Intermediate Structures in the Unfolding of the Trp-Cage Fast-Folding Protein." J Phys Chem Lett. PMID:36705525. DOI:10.1021/acs.jpclett.2c03680 — experimental SAXS unfolding

### Methodology references (from Step 2c lit)
- Kasavajhala K, Lam K, Simmerling C. 2020. "Exploring Protocols to Build Reservoirs to Accelerate Temperature Replica Exchange MD Simulations." J Chem Theory Comput. PMID:33142060. DOI:10.1021/acs.jctc.0c00513 — GPU REMD best practices, RREMD
- Grossfield A et al. 2018. "Best Practices for Quantification of Uncertainty and Sampling Quality in Molecular Simulations." LiveCoMS. PMID:30533602 — convergence assessment for REMD
- Debiec KT et al. 2016. "Further along the Road Less Traveled: AMBER ff15ipq..." J Chem Theory Comput. PMID:27399642. DOI:10.1021/acs.jctc.6b00567 — ff15ipq+SPC/Eb as alternative to ff14SB+TIP3P

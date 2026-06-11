# STUDY REPORT — Study 098: Ubiquitin (1UBQ) 100 ns MD vs NMR Conformational Ensemble

## 1. Objective
Run a 100 ns explicit-solvent MD simulation of human ubiquitin (PDB 1UBQ) and compare the
sampled conformational ensemble to solution-NMR dynamics data, focusing on:
- **C-terminal tail flexibility** (residues 71–76, the Leu-Arg-Gly-Gly tail)
- **β1–β2 loop dynamics** (residues ~7–11, the "Lys11 loop"/β-hairpin turn)

Primary NMR-comparable observable: **per-residue backbone N–H Lipari–Szabo S² order
parameters** (computed by isotropic reorientational eigenmode dynamics, IRED), supported by
backbone RMSF and radius of gyration.

## 2. System
| Property | Value | Source |
|----------|-------|--------|
| PDB | 1UBQ (X-ray, 1.8 Å, monomeric, UniProt P62988) | `raw_pdbs/1UBQ.pdb` |
| Residues | 76 (Met1–Gly76), full-length, no missing residues/gaps | preflight PASS |
| Force field | ff19SB (protein) + OPC (water) | Amber24 manual p.33–34, 54 |
| Ions | 13 Na⁺ / 13 Cl⁻ ≈ 0.15 M NaCl (net charge 0) | `system/tleap.log` |
| Box | truncated octahedron, 10 Å padding, 4656 OPC waters, 19,777 atoms | `system/tleap.log` |
| Engine | pmemd.cuda, dt 2 fs, SHAKE (ntc=2/ntf=2), PME cut 10 Å, 300 K / 1 bar | `simulations/prod/prod.mdin` |

## 3. Protonation Rationale
pH 7.2 (cytoplasmic/nuclear compartment; ubiquitin is a cytosolic/nuclear protein).
propka3 (`system/protein_only.pka`): all Asp/Glu deprotonated, all Lys/Arg protonated,
Tyr59 neutral. **Only His68** is non-standard: pKa 6.0 < pH 7.2 → neutral, assigned **HID**
(δ-tautomer, propka3 default, no clear H-bond donor). Net charge = 0.000 (`charge_check.log`).

## 4. Methods (actual mdin values used)
- **Min1** (`simulations/min1/min1.mdin`): imin=1, maxcyc=5000, ncyc=2500, ntr=1 restraint_wt=10 on `@CA,C,N`, cut=10.
- **Min2**: imin=1, maxcyc=5000, unrestrained.
- **Heat** (`heat.mdin`): NVT, nstlim=100000 (200 ps), dt=0.002, ntt=3 γ=1.0, 0→300 K via &wt TEMP0 ramp, backbone restraint_wt=5.
- **Equil** (`equil.mdin`): NPT, nstlim=250000 (500 ps), barostat=1 (Berendsen, taup=1.0), backbone restraint_wt=1, ntwr=2500.
- **Equil2** (`equil2.mdin`): NPT, nstlim=250000 (500 ps), barostat=2 (MC), unrestrained.
- **Production** (`prod.mdin`): NPT, **nstlim=50,000,000 (100 ns)**, dt=0.002, ntt=3 γ=1.0, barostat=2 (MC), temp0=300, ntwx=5000 → **10,000 frames (10 ps/frame)**, ig=-1.
- **Analysis**: cpptraj autoimage; RMSD/RMSF/radgyr; N–H S² via IRED (`vector :i@N ired :i@H`; `matrix ired order 2`; `diagmatrix vecs 72`; `ired relax freq 600 NHdist 1.02 order 2 modes ired.vec orderparamfile`) over 72 N–H bonds (res 2–76 excl. Pro19/37/38), Amber24 manual p.854–855.

## 5. Results
All values from production trajectory (100 ns, 10,000 frames).

### 5.1 Stability & convergence
| Observable | Value | File |
|-----------|-------|------|
| Core CA RMSD (res 1–72) | mean **0.89 Å** (std 0.11), drift 0.06 Å | `analysis/rmsd_core_CA.dat` |
| All-CA RMSD (1–76) | mean 1.66 Å (std 0.38) — inflated by tail | `analysis/rmsd_allCA.dat` |
| Radius of gyration | mean **11.83 Å** (std 0.10), drift 0.009 Å | `analysis/rgyr.dat` |
| Production avg T / density | 300.04 K / 1.0274 g/cc | `simulations/prod/prod.mdout` AVERAGES |

### 5.2 Per-residue backbone flexibility (RMSF, CA) — `analysis/rmsf_CA.dat`
- Global mean 0.94 Å; range 0.42 → 6.92 Å.
- **C-terminal tail peaks**: res73=1.90, res74=2.82, res75=4.46, **res76=6.92 Å**.
- **β1–β2 loop peaks**: res8=1.46, res9=1.43, res10=1.27 Å.
- Secondary loop: res47≈1.24 Å.

### 5.3 N–H order parameters S² (IRED) — `analysis/s2_by_residue.dat`
| Region | S² | Interpretation |
|--------|----|----|
| Folded core (res 2–70 mean) | **0.840** | rigid β-sheet/α-helix |
| β1–β2 loop res8 / 9 / 10 / 11 | 0.78 / 0.75 / **0.66** / **0.66** | modestly flexible (Lys11 loop) |
| C-term Leu71 / Arg72 / Leu73 | 0.78 / 0.74 / **0.48** | onset of tail mobility |
| C-term Arg74 / Gly75 / Gly76 | **0.087 / 0.044 / 0.021** | near-free internal motion |
| Overall (72 vectors) | mean 0.800, min 0.021, max 0.926 | |

### 5.4 C-terminal tail metric — `analysis/tail_to_core.dat`
Gly76(CA)→core(res2–72 CoM) distance: mean 22.9 Å, std 2.97 Å (large fluctuation = mobile tail).

Plots: `analysis/{rmsd_core_CA,rgyr,s2_by_residue,rmsf_CA}.png`.

## 6. Convergence Assessment
- Core fold **converged**: CA RMSD plateau 0.89 Å, half-to-half drift 0.06 Å; Rg drift 0.009 Å.
- C-terminal tail and β1–β2 loop are **intrinsically mobile** (high RMSF, low S²), not drift —
  expected and physically correct, not a convergence failure.
- The fast (ps–ns) N–H motions that S² probes are well sampled in 100 ns for a rigid globular
  fold; block consistency (core RMSD 1st 0.857 / 2nd 0.914 Å) supports convergence of the relevant timescales.

## 7. Key Findings
1. **The C-terminal tail (71–76) is the dominant flexible element** (§5.2, §5.3): S² collapses
   monotonically from ~0.78 (Leu71) to ~0.02 (Gly76) and RMSF rises to 6.9 Å at Gly76. This
   reproduces the hallmark NMR ubiquitin S² signature where the LRGG tail is essentially
   freely reorienting — directly relevant to its role as the isopeptide-conjugation handle.
2. **The β1–β2 (Lys11) loop is the most mobile structured region** (§5.2, §5.3): S² ≈ 0.66 at
   res10–11 and RMSF ≈ 1.3–1.5 Å at res8–10, distinctly above the ~0.84 rigid-core baseline —
   matching the moderate enhanced flexibility seen for this loop in NMR relaxation studies.
3. **The folded core is rigid and stable** (§5.1, §5.3): core CA RMSD 0.89 Å and mean core
   S² 0.84 confirm ff19SB/OPC maintains the native fold over 100 ns, consistent with the
   Amber24 manual's ubiquitin benchmark (≈1.0–1.2 Å backbone RMSD).
4. **Global compactness is invariant** (§5.1): Rg 11.83 ± 0.10 Å — the protein neither unfolds
   nor over-compacts, indicating a balanced protein–water interaction in ff19SB/OPC.

## 8. Caveats & Limitations
- **Timescale**: 100 ns converges fast (ps–ns) N–H S² but does NOT sample the slow (µs)
  collective "open/closed pincer" motion of ubiquitin resolved by RDC/EROS ensembles
  (Lange et al. 2008). Reported S² therefore captures fast local flexibility, not the full
  µs conformational heterogeneity.
- **Single replica, single seed** — no inter-replica error bars; convergence assessed by
  block (1st/2nd half) consistency only.
- **S² from a single trajectory** depends on separating internal from global tumbling; the
  cpptraj IRED matrix handles this internally (appropriate), but absolute S² magnitudes for
  the most mobile tail residues are sensitive to tcorr (10 ns) truncation.
- **Force field trade-off**: ff19SB/OPC chosen for backbone-dynamics fidelity; for pure X-ray
  RMSD ff14SB was marginally tighter on ubiquitin (manual p.54, 1.0 vs 1.2 Å).
- No direct numerical fit (e.g. RMSD between simulated and experimental S² vectors) was
  performed — comparison is qualitative/profile-level against established NMR S² benchmarks.

## 9. Comparison to Literature
Ubiquitin is the canonical benchmark for protein NMR backbone dynamics. The simulated S²
profile reproduces the textbook experimental pattern: rigid core S² ≈ 0.8–0.85; sharp tail
collapse over res 73–76; modestly reduced β1–β2 loop (Schneider, Brüschweiler, Wright,
*Biochemistry* 1992; Tjandra, Feller, Pastor, Bax, *JACS* 1995; Lange et al., *Science* 2008
EROS ensemble of 1UBQ). PubMed-retrieved methodologically-relevant studies:
- **Phan TM, Mohanty P, Mittal J (2025)** *Nat Commun* 16, PMID 41298416, DOI 10.1038/s41467-025-65603-4 — Amber protein-FF refinement validated against NMR S²/SAXS; confirms ff19SB-class FFs maintain folded-protein stability over µs (consistent with our stable core).
- **Lesovoy D et al. (2025)** *Int J Mol Sci* 26:8917, PMID 41009484, DOI 10.3390/ijms26188917 — MD + amide ¹⁵N(¹H) relaxation ensembles selected by RMSD-plateau segments; methodological precedent for MD-vs-NMR-relaxation comparison.
- **Bhattacharya S, … Palmer AG (2025)** *J Magn Reson*, PMID 41172913, DOI 10.1016/j.jmr.2025.107989 — ¹⁵N relaxometry of human ubiquitin (experimental dynamics reference for this exact protein).
- **Xiong C, … Tao P (2026)** *J Chem Theory Comput*, PMID 41481844, DOI 10.1021/acs.jctc.5c01579 — generative sampling resolves ubiquitin C-terminal-region conformational states, corroborating tail as the dominant flexible element.

## 10. Data Files
- Topology/coords: `system/system.prmtop`, `system/system.inpcrd`
- Trajectory: `simulations/prod/prod.nc` (2.37 GB, 10,000 frames, 100 ns)
- Restart: `simulations/prod/prod.rst7`
- Analysis data: `analysis/s2_by_residue.dat`, `ired_s2_order.dat`, `rmsf_CA.dat`, `rmsf_NH.dat`, `rmsd_core_CA.dat`, `rmsd_allCA.dat`, `rgyr.dat`, `tail_to_core.dat`
- Plots: `analysis/s2_by_residue.png`, `rmsf_CA.png`, `rmsd_core_CA.png`, `rgyr.png`
- Logs: `logs/*.out`, `logs/*.err`; engineering log `PROCESS_REPORT.md`; plan `PLAN.md`

## 11. References
1. Tian C, et al. ff19SB. *J Chem Theory Comput* 2020, 16, 528. (Amber24 manual p.34)
2. Izadi S, Anandakrishnan R, Onufriev AV. OPC water. *J Phys Chem Lett* 2014, 5, 3863. (manual p.53)
3. Amber 2024 Reference Manual — ff19SB/OPC (p.33–34, 54); cpptraj IRED S² (p.854–855); SHAKE/dt (p.397).
4. Schneider DM, Brüschweiler R, Wright PE. *Biochemistry* 1992, 31, 3645 (ubiquitin S²).
5. Lange OF, et al. *Science* 2008, 320, 1471 (EROS ensemble, 1UBQ µs motion).
6. Phan TM, Mohanty P, Mittal J. *Nat Commun* 2025, PMID 41298416.
7. Lesovoy D, et al. *Int J Mol Sci* 2025, 26, 8917, PMID 41009484.
8. Bhattacharya S, Goger M, Dahmane T, Palmer AG. *J Magn Reson* 2025, PMID 41172913.
9. Xiong C, et al. *J Chem Theory Comput* 2026, PMID 41481844.

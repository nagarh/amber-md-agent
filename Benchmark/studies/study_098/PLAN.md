# PLAN — Study 098: Ubiquitin (1UBQ) 100 ns MD vs NMR conformational ensemble

## Objective
Simulate human ubiquitin (PDB 1UBQ) for 100 ns explicit-solvent MD and compare the
conformational ensemble to solution-NMR data, with focus on:
- **C-terminal tail flexibility** (residues 71–76, LRGG tail)
- **β1–β2 loop dynamics** (residues ~7–11, the "Lys11 loop"/β1–β2 hairpin turn)

Primary observable for NMR comparison: **per-residue backbone N–H Lipari–Szabo S²
order parameters** (lower S² = higher ps–ns flexibility), plus backbone RMSF.

## System (from preflight — PASS)
| Property | Value |
|----------|-------|
| PDB | 1UBQ (X-ray, 1.8 Å, monomeric) |
| Chains | A (single) |
| Residues | 76 (Met1–Gly76), full-length, no missing residues |
| Coordinate gaps | none |
| Ligands / metals | none |
| Disulfides | none (ubiquitin has no Cys) |
| Crystal waters | 58 — stripped (rebuilt by solvation) |
| His | His68 only |
| C-terminus | free COO⁻ (OXT present on Gly76) |
| Net charge (tLEaP `charge`) | **0.000000** → `system/charge_check.log` |

## Protonation states (pH 7.2)
**pH 7.2 — cytoplasmic/nuclear compartment.** Ubiquitin is a cytosolic/nuclear protein
(UniProt P62988); its NMR dynamics data are recorded in near-neutral buffer.
Tier 3 (training) for the compartment→pH mapping; propka3 confirms all titratable
residues are in standard states at this pH.

| Residue | propka3 pKa | State | Rationale |
|---------|-------------|-------|-----------|
| His68 | 6.00 | **HID** | pKa 6.0 < pH 7.2 → neutral; no clear H-bond donor → δ-tautomer (HID), propka3 default |
| All Asp (21,32,39,52,58) | 2.99–3.92 | ASP⁻ | pKa ≪ pH → deprotonated |
| All Glu (16,18,24,34,51,64) | 3.99–4.78 | GLU⁻ | pKa ≪ pH → deprotonated |
| All Lys (6,11,27,29,33,48,63) | 10.3–11.0 | LYS⁺ | pKa ≫ pH → protonated |
| All Arg (42,54,72,74) | 12.1–12.8 | ARG⁺ | protonated |
| Tyr59 | 9.99 | TYR | protonated (neutral) |

No non-standard states other than His68→HID. propka3 output: `system/protein_only.pka`.

## Force fields (tier protocol)
| Component | Choice | Tier / Justification | Manual validation |
|-----------|--------|----------------------|-------------------|
| Protein | **ff19SB** | Tier 2 (Amber24 manual p.33: "recommended choice is ff19SB"). ff19SB uses residue-specific φ/ψ CMAPs fit to QM solution surfaces → best available reproduction of backbone Ramachandran/amino-acid-specific dynamics, directly relevant to per-residue S² comparison. | `rag_query` p.34–35 confirms `leaprc.protein.ff19SB` |
| Water | **OPC** | Tier 2 (Amber24 manual p.34: "we strongly recommend using ff19SB with OPC, and we recommend against use with TIP3P"). Manual p.54 explicitly benchmarks ubiquitin with ff19SB/OPC-family (≈1.2 Å backbone RMSD, multi-µs stable). | `rag_query` p.53 confirms `leaprc.water.opc`, `OPCBOX` |
| Ions | **Joung–Cheatham / Li–Merz monovalent (auto-loaded by leaprc.water.opc)** | Tier 2 (manual p.53–54: leaprc.water.opc auto-loads JC monovalent + Li/Merz 12-6 OPC ion params). | `charge_check.log` shows `frcmod.ionslm_126_opc` loaded |

**Note on FF for NMR-S² comparison:** ff19SB+OPC is the current Amber-recommended pairing
and the literature standard for reproducing protein backbone order parameters. Trade-off
noted in manual p.54: for *X-ray RMSD stability* alone ff14SB was marginally tighter
(1.0 vs 1.2 Å), but for *dynamics/flexibility* (S², the target observable here) the
QM-derived ff19SB backbone is preferred. Caveat recorded in §Caveats.

## Box & ions
| Parameter | Value | Justification |
|-----------|-------|---------------|
| Box shape | truncated octahedron (`solvateOct`) | ~25% fewer waters than cubic for a globular monomer → faster; standard for compact proteins |
| Padding | 10.0 Å | Tier 2: OPC benchmarked at 8 Å cutoff (manual p.53); 10 Å solute–wall buffer ≥ cutoff prevents periodic self-interaction of the flexible C-terminal tail, which extends from the fold. Conservative for a small (76-res) protein on GPU. |
| Neutralizing ions | none needed (net charge 0) | `charge_check.log` = 0.000 |
| Background salt | **0.15 M NaCl** via `addIonsRand` after solvation | matches physiological / NMR-buffer ionic strength so electrostatics of surface Lys/Arg (incl. Lys11, Lys48, Lys63) are screened realistically |

## Simulation protocol
RAG-validated parameters (`rag_query` SHAKE/dt p.397, restraint protocol p.386/391, GPU PME p.461).
Engine: **pmemd.cuda** (GPU). dt = 2 fs with SHAKE on H bonds (ntc=2, ntf=2). cut = 10.0 Å, PME.

| Step | Engine | Ensemble | nstlim / maxcyc | dt | Restraints | Notes |
|------|--------|----------|-----------------|----|-----------|-------|
| Min1 | pmemd.cuda | — | maxcyc=5000 (ncyc=2500) | — | backbone `@CA,C,N` restraint_wt=10 | relax waters/H, hold solute |
| Min2 | pmemd.cuda | — | maxcyc=5000 (ncyc=2500) | — | none | full relaxation |
| Heat | pmemd.cuda | NVT | 100000 (200 ps) | 0.002 | backbone `@CA,C,N` restraint_wt=5 | 0→300 K, Langevin ntt=3 γ=1.0 |
| Equil | pmemd.cuda | NPT | 250000 (500 ps) | 0.002 | backbone `@CA,C,N` restraint_wt=1 | Berendsen barostat (barostat=1), density burst, ntwr=2500 |
| Equil2 | pmemd.cuda | NPT | 250000 (500 ps) | 0.002 | none | MC barostat (barostat=2), unrestrained settle |
| Production | pmemd.cuda | NPT | **50,000,000 (100 ns)** | 0.002 | none | MC barostat, ntt=3 γ=1.0, ntwx=5000 (10 ps/frame → 10,000 frames), ig=-1 |

**Temperature 300 K**, **pressure 1 bar**. T justified: 1UBQ NMR-dynamics reference data
(Lipari–Szabo S², RDC ensembles) recorded near 300 K (Tjandra/Bax; Lange et al. 2008); 300 K is the OPC validated regime (manual p.54).

**Production length 100 ns:** user-specified. Sufficient to converge backbone RMSF / S² for
fast (ps–ns) N–H motions of a rigid globular fold; the C-terminal tail and β1–β2 loop motions
are sub-ns and well-sampled at 100 ns. (Slow µs collective "pincer" motions are NOT fully
sampled at 100 ns — caveat recorded.)

## Analysis targets
1. **Backbone RMSD** vs 1UBQ crystal (CA, res 1–72 core, excl. flexible tail) → stability/convergence.
2. **Per-residue backbone RMSF** (CA and N–H) → identify mobile regions; expect peaks at C-term tail (71–76) and β1–β2 loop (7–11).
3. **N–H order parameters S²** via cpptraj IRED (`vector ... ired`, `matrix ired`, `diagmatrix`, `ired order 2`) → direct comparison to NMR Lipari–Szabo S² (manual p.855).
4. **Radius of gyration** time series → global compactness.
5. **C-terminal tail end-to-end / Gly76–core distance** → tail flexibility metric.
6. Convergence: RMSD plateau (`check_convergence`), block-averaged S² over 1st/2nd half.

Reference NMR S²: classic ubiquitin backbone S² (Schneider et al. 1992; Tjandra et al. 1995/1997;
ensemble S² Lange et al. 2008) — core β-sheet/α-helix S² ≈ 0.8–0.9; C-terminal tail S² drops
sharply (Leu73 ≈ 0.6, Arg74 ≈ 0.4, Gly75 ≈ 0.2, Gly76 ≈ 0.1); β1–β2 loop modestly reduced (~0.7–0.8).

## Literature precedent (Step 2b)
Ubiquitin is the canonical benchmark system for protein NMR dynamics / S² order parameters.
PubMed search "ubiquitin conformational dynamics NMR order parameters MD" (1899 hits) — selected:
- **Bhattacharya S, … Palmer AG (2025)** *J Magn Reson* PMID 41172913 — ¹⁵N relaxometry of human ubiquitin (validation of relaxation→dynamics analysis). DOI 10.1016/j.jmr.2025.107989.
- **Phan TM, Mohanty P, Mittal J (2025)** *Nat Commun* PMID 41298416 — protein–water-balanced Amber FFs validated against NMR S²/SAXS; folded-protein stability. DOI 10.1038/s41467-025-65603-4.
- **Alhossary A, Smith CA (2026)** *J Phys Chem B* PMID 41801005 — synthetic ubiquitin ensembles, NOE/RDC dynamic refinement (S²/angular fluctuations). DOI 10.1021/acs.jpcb.5c08554.
- **Xiong C, … Tao P (2026)** *J Chem Theory Comput* PMID 41481844 — ubiquitin C-terminal-region conformational states from trajectory sampling. DOI 10.1021/acs.jctc.5c01579.

Classic experimental S² references (to cite in STUDY_REPORT for the actual comparison):
Schneider DM, Brüschweiler R, Wright PE (1992); Tjandra N, Feller SE, Pastor RW, Bax A (1995);
Lange OF et al. *Science* 2008 (EROS ensemble of 1UBQ). These are the de-facto S² benchmark.

## Method best practices (Step 2c)
**Step 2c trigger:** keyword "NMR restraint" / "order parameter" comparison — but this is a
*plain unrestrained NPT MD* whose output is *compared* to NMR (not NMR-restrained MD). No
specialized Amber method (TI/REMD/GaMD) is used. The only method-specific requirement is the
**cpptraj IRED S² analysis** (manual p.855), already RAG-confirmed. Standard NPT MD protocol
applies. No alchemical/enhanced-sampling flags needed.

## Walltime estimates
- Prep (tLEaP, charge check): minutes (done/queued, CPU).
- Min→Equil2 (Batch 1+start of 2): < 1 h GPU.
- Production 100 ns, ~12k-atom system on 1 GPU: ~150–300 ns/day expected → ~8–16 h. Walltime request 48:00:00 (single GPU) with restart-on-walltime fallback.
- Analysis (cpptraj IRED + RMSF + Rg): < 1 h CPU.

## Caveats / limitations
- **100 ns samples fast (ps–ns) N–H dynamics** that S² probes; it does NOT converge slow µs
  collective ubiquitin motions (the "open/closed" pincer mode seen in RDC/EROS ensembles).
  S² for rigid core and fast tail/loop motions IS meaningful at 100 ns.
- **S² from a single 100 ns trajectory** is sensitive to overall-tumbling removal; cpptraj IRED
  separates internal from global motion via the iRED matrix — appropriate here.
- ff19SB+OPC: chosen for dynamics fidelity; for pure X-ray RMSD ff14SB was marginally tighter
  (manual p.54). Reported as a force-field caveat, not a build error.
- Single replica — no statistical error bars across independent runs; block analysis (1st vs 2nd
  half) used as a convergence proxy.

## Approval: APPROVED 2026-06-10 (autonomous benchmark execution)

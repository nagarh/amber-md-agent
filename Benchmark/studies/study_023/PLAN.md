# Plan — study_023 (Dickerson dodecamer 1BNA, B-DNA, OL21, 50 ns)
Date: 2026-06-06

## System (from preflight)
- PDB: 1BNA, Dickerson-Drew dodecamer d(CGCGAATTCGCG)₂
- Biological unit: DIMERIC duplex. REMARK 350 BIOMT = 1 identity operator. Chains A (res 1–12) + B (res 13–24) in the asymmetric unit ARE the complete duplex. The preflight `biological_assembly` FAIL is a **confirmed false positive** — no BIOMT transform needed (operator is identity; both strands already present). Verified by residue listing: A = CGCGAATTCGCG, B = complementary strand.
- Chains kept: A + B (full duplex). Crystallographic waters (80 HOH) stripped by pdb4amber; fresh OPC solvent added.
- Atom count: 486 DNA heavy atoms (566 incl. crystal waters) → ~7,000–8,000 atoms after solvation (estimate).
- Special features: 5'-OH termini (no terminal phosphate — pdb4amber renames DC5/DG3 etc.). No ligands, metals, modified residues, disulfides, gaps, or alt-locs.

## Force fields

### FF table

| Component | Choice | Lit precedent (PMID) | Manual page | Reason for this study |
|-----------|--------|---------------------|-------------|------------------------|
| DNA | OL21 (`leaprc.DNA.OL21`) | 39748297 (Zgarbová 2025, OL21 keeps accurate B-DNA); 39012172 (Knappeová 2024, OL21 benchmark on Dickerson-Drew) | Amber24 §3.2.2 p.40, Table 3.2 p.41 | User-specified; manual's current recommended DNA FF, explicitly tested on the Dickerson-Drew dodecamer (p.40) |
| Water | OPC (`leaprc.water.opc`, OPCBOX) | 39012172 (OPC used with AMBER NA FFs) | Amber24 §3.6.1 p.53–54 | Manual states OPC "improves structural description of DNA duplex" (p.54); recommended modern model |
| Ions | K⁺/Cl⁻ Joung–Cheatham (auto-loaded with `leaprc.water.opc`) | 18593145 (JC ions) | Amber24 §3.6 p.53, §13.6.5 p.249 | K⁺ is the physiological DNA counter-ion; JC monovalent params load automatically with the OPC leaprc |

OL21 supersedes OL15/bsc1 (manual p.40: "now our recommended DNA force field"). RAG-validated: `leaprc.DNA.OL21` and `leaprc.water.opc` both exist in Amber 24.

## Protonation states
- DNA has no titratable bases at pH ~7 (standard Watson–Crick canonical protonation). No propka3 needed (propka3 is for protein residues). All bases in default protonation (N1/N3 canonical).
- pH context: ~7 (neutral, physiological/solution-NMR reference). No non-standard states.

## Simulation Conditions

| Condition | Value | Reason / source |
|-----------|-------|-----------------|
| Production temperature | 300 K | Common MD reference T for solution B-DNA; matches AMBER NA-FF validation studies (Knappeová 2024 PMID 39012172) and manual MD example (p.386). Helical params are equilibrium observables. |
| Pressure | 1 atm | NPT solution standard |
| pH | ~7 | Canonical DNA, no titratable groups |
| Ionic strength | Neutralize + ~150 mM KCl | DNA helical geometry (esp. groove width, twist) is salt-sensitive; ~150 mM is physiological. Counts computed from solvated water number per study (not hardcoded). |

## Simulation Protocol

| Step | Setting | Time / cycles | Manual / lit source |
|------|---------|---------------|---------------------|
| Min1 | restrained DNA `:1-24` @ 10 kcal/mol·Å² (relax solvent/ions) | 2000 cyc (ncyc 1000 SD→CG) | Amber24 §21.6.4–21.6.5 p.391; restrained-min example p.386 |
| Min2 | full, unrestrained | 5000 cyc (ncyc 2000) | Amber24 §21.6.5 p.391 |
| Heat | NVT 0→300 K, Langevin ntt=3 γ=5.0, restrained DNA `:1-24` @ 10 kcal/mol·Å², SHAKE ntc=2/ntf=2, dt=0.002 | 100 ps (50,000 steps) | Amber24 §21.6 plain-MD example p.386 (ntt=3, γ=5.0); DNA7 test cut=9.0 p.407 |
| Burst density | NPT, barostat=1 (Berendsen) taup=2.0, restrained DNA @ 5 kcal/mol·Å², ntwr=500 | 200 ps (100,000 steps) | amber-workflow.md §burst (Berendsen during density burst); manual taup=2.0 p.386 |
| Equil2 | NPT, barostat=2 (MC) taup=2.0, restraint released 5→0 over two sub-steps then unrestrained | 500 ps (250,000 steps) | Amber24 §21.6 p.386; workflow.md (MC barostat once near target density) |
| Production | NPT, MC barostat (barostat=2) taup=2.0, no restraint, ntt=3 γ=5.0, dt=0.002, cut=9.0, iwrap=1 | 50 ns (25,000,000 steps) | User prompt (50 ns); cut=9.0 from DNA7 manual test p.407 |

### Production length reasoning
- User specified 50 ns verbatim → source = **user prompt**.
- Helical-parameter convergence (rise/twist/roll) for a 12-mer B-DNA duplex is reached well within tens of ns; precedent FF-benchmark studies (Knappeová 2024) use 1–2 µs for fine FF discrimination but report stable helical averages on much shorter windows. 50 ns is adequate for ensemble-averaged helical descriptors with a crystallographic comparison; longer µs runs would only tighten error bars. Caveat noted in §Caveats.

### Equil2 sizing
- Tiny system (<15k atoms) → fast density recovery. Burst (200 ps) + Equil2 (500 ps) sufficient to reach ~1.0 g/cc OPC density and 300 K plateau before production.

## Box
- Solvent: OPC (OPCBOX).
- Shape/padding: truncated octahedron (`solvateOct`), 10.0 Å buffer, `iso` flag (elongated rod-like duplex → isometric octahedron minimizes water count while keeping min-image distance). 10 Å pad > cut (9.0 Å) + drift buffer, satisfying minimum-image (Amber24 §13.6.42 p.263).
- Ions: neutralize with K⁺ (`addIons mol K+ 0`; net charge expected ≈ −22 for the 22 internal phosphates), then add ~150 mM KCl as explicit K⁺/Cl⁻ pairs computed from the actual solvated water count (n_pairs ≈ 0.0027 × n_waters). Two-pass tLEaP: pass 1 solvate+neutralize → read water count → pass 2 with salt. (Amber24 §13.6.5 p.249.)

## Analysis targets
- **Primary (study objective):** helical base-pair-step parameters via cpptraj `nastruct` — **rise, twist, roll** (per-step + duplex averages), compared to 1BNA crystallographic values.
- Supporting: shift/slide/tilt step params, base-pair params, backbone RMSD vs crystal (terminal bp excluded — fraying expected), per-residue RMSF, minor/major groove widths (sanity check vs B-form ~6/~11 Å).
- Convergence: RMSD plateau + block-averaged helical params over trajectory halves.

## Literature precedent (Step 2b)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable |
|------------------------|--------|------------|-----|------------------------|
| Knappeová et al. 2024, PMID 39012172, DOI 10.1021/acs.jctc.4c00601 | Dickerson-Drew dodecamer (DNA/RNA hybrid benchmark, incl. dsDNA) | µs | OL21/bsc1 + others | helical params, pucker, inclination vs experiment |
| Zgarbová et al. 2025, PMID 39748297, DOI 10.1021/acs.jctc.4c01100 | B-DNA duplexes (A/B equilibrium) | — | OL15/OL21/bsc1/OL24 | OL21 maintains accurate canonical B-DNA; twist, pucker |
| Tucker et al. 2022, PMID 35694853, DOI 10.1021/acs.jpcb.1c10971 | ds-DNA incl. dodecamers | — | DES-Amber/AMBER | helical/thermal stability of dsDNA |

## Method best practices (Step 2c)
Standard NPT MD of a canonical B-DNA duplex — no enhanced-sampling / alchemical / metal / membrane keyword triggers. Step 2c not required (nucleic-acid skill loaded for prep specifics). No Step 2c deviations.

## Walltime estimates
| System size | ns/day | This study walltime |
|-------------|--------|---------------------|
| ~7–8k atoms (tiny), pmemd.cuda 1 GPU | ~150–300 ns/day | min+heat+equil ~30 min; prod 50 ns ≈ 4–8 h → request 24:00:00 |

## Caveats / limitations
- 50 ns gives reliable ensemble-averaged helical descriptors but is short relative to µs FF-benchmark studies; reported as time-averaged ± SD, not converged sub-state populations.
- Terminal base pairs fray in B-DNA MD — terminal bp excluded from RMSD and de-emphasized in helical averages.
- Crystal helical values reflect lattice packing; solution MD legitimately differs (esp. twist, groove widths). Comparison is qualitative agreement within ~B-form ranges.

## Approval: APPROVED 2026-06-06 (autonomous benchmark run — execution directive authorizes continuous build→production→analysis without interactive gate; all parameters justified per tier protocol above)

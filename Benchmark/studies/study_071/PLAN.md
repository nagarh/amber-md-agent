# Plan — study_071: BPTI (5PTI) stability MD

Date: 2026-06-09

## System (from preflight)
- PDB: 5PTI (bovine pancreatic trypsin inhibitor, BPTI), monomeric
- Biological unit: MONOMERIC (REMARK 350: 1 operator, chain A)
- Chains kept: A only (58 residues, full-length, residues 1–58)
- Atom count: 454 protein heavy atoms (H rebuilt by tLEaP); solvated system ≈ 12–14k atoms
- Special features:
  - 3 disulfide bonds: Cys5–Cys55, Cys14–Cys38, Cys30–Cys51 (CYS→CYX, CONECT records)
  - **Neutron/X-ray structure (1.00 Å)** — original PDB contains deuterium (element D) atoms; all D and H stripped, heavy atoms only retained, tLEaP rebuilds protons
  - HETATM stripped: DOD (crystallographic D2O), PO4 (phosphate buffer — not functional), UNX (1 unidentified atom). None functionally relevant to the apo stability question → protein-only in fresh solvent.
  - Alternate conformers (GLU7, MET52): kept conformer A (higher occupancy), altloc column blanked.
  - No HIS, no metals, no cofactor.

## Force fields

### FF table

| Component | Choice | Lit precedent (PMID) | Manual page | Reason for this study |
|-----------|--------|---------------------|-------------|------------------------|
| Protein   | ff19SB | Tier 2 (manual); BPTI MD precedent PMID:36499117 used AMBER ff-class | Amber24 §3 / §3.1.1 p.33–34 | Latest SB protein FF; residue-specific CMAP improves backbone/Ramachandran fidelity — directly relevant to a backbone-RMSD stability test |
| Water     | OPC    | Tier 2 (manual) | Amber24 §3 p.33–34, §3.6 p.52 | Manual: ff19SB "pairs best with OPC"; TIP3P explicitly discouraged with ff19SB (QM-based dihedrals) |
| Ions      | Cl⁻ (Joung–Cheatham, monovalent) | Tier 2 (manual) | Amber24 §3.6/§3.7 | Neutralize net +6 charge; monovalent ion params loaded with leaprc.water.opc |

**Manual validation (anti-hallucination):**
- `leaprc.protein.ff19SB` — confirmed real, Amber24 §3.1.1 p.34–35 (RAG)
- `leaprc.water.opc` — confirmed real, Amber24 §3.6 p.52 (RAG)
- ff19SB+OPC pairing explicitly recommended by manual (RAG p.33–34) — not a hallucinated combination.

## Protonation states
- pH chosen: **7.4** — BPTI is a secreted/extracellular Kunitz-type serine-protease inhibitor; extracellular compartment → pH 7.4 (Tier 3 compartment reasoning; consistent with physiological function). propka3 confirms all titratable residues are in standard states at this pH, so the choice is not sensitive within 7.0–7.4.
- propka3 run on starting structure: yes — `system/protein_cyx.pka` (pH 7.4)

| Residue | State | Rationale |
|---------|-------|-----------|
| All ASP/GLU | deprotonated (standard) | propka3 pKa 3.7–5.37 ≪ 7.4 |
| All LYS/ARG | protonated (standard) | propka3 pKa 10.1–12.6 ≫ 7.4 |
| All TYR | protonated (standard) | propka3 pKa ~10 ≫ 7.4 |
| Cys5/14/30/38/51/55 | CYX (disulfide) | 3 SS bonds from SSBOND records — not titratable |
| (no HIS in BPTI) | — | — |

No non-standard protonation overrides applied — propka3 `suggested_overrides` empty.

## Simulation Conditions

| Condition | Value | Reason / source |
|-----------|-------|-----------------|
| Production temperature | 300 K | User prompt specifies 300 K explicitly; also common BPTI MD reference T |
| Pressure | 1 atm | NPT solution standard |
| pH | 7.4 | see §Protonation |
| Ionic strength | neutralize-only (6 Cl⁻) | Stability/structure question; no electrostatic-screening requirement → minimal counter-ions only (Amber24 §13.6.5 p.249) |

## Simulation Protocol

| Step | Setting | Time / cycles | Manual / lit source |
|------|---------|---------------|---------------------|
| Min1 | restrained backbone (@CA,C,N) 10 kcal/mol·Å², steepest→CG | 5000 cyc (ncyc=2500) | Amber24 §21.6 p.386 (restrained min example) |
| Min2 | full, no restraint | 5000 cyc (ncyc=2500) | Amber24 §21.6 p.386 |
| Heat | NVT 0→300 K, Langevin γ=5.0, restrained backbone 10 kcal/mol·Å², dt=0.002, SHAKE | 100 ps (50000 steps) | Amber24 §21.6 p.386 (ntt=3,gamma_ln=5.0); §21.6.8 p.395 (heat at NVT before NPT) |
| Burst density | NPT, Berendsen barostat=1, taup=2.0, restrained backbone 5 kcal/mol·Å², dt=0.002 | 200 ps (100000 steps), ntwr=500 | Amber24 §21.6.8 p.395 (Berendsen for density); amber-workflow burst guidance |
| Equil2 | NPT, MC barostat=2, no restraint, dt=0.002 | 500 ps (250000 steps) | Amber24 §21.6.8 p.395; §22.6 p.461 (MC barostat for production-quality NPT) |
| Production | NPT, MC barostat=2, no restraint, dt=0.002, SHAKE | **100 ns** (50,000,000 steps) | User prompt = 100 ns; Amber24 §21.6 p.386 plain-MD template |

### Production length reasoning
1. User prompt specifies **100 ns** verbatim → source = user prompt.
2. BPTI is a small, rigid, disulfide-locked globular protein; backbone RMSD plateaus within a few ns. 100 ns far exceeds the timescale needed to assess structural stability against the crystal structure — convergence expected well before end.
3. Walltime budget: small system (~13k atoms) on 1 GPU → ample; 100 ns achievable in one or two SLURM windows.

### Equil2 sizing reasoning
- System tiny (<15k atoms): burst density converges fast; 500 ps NPT equil2 after burst is generous for a small rigid protein to relax into target density and recover T after the Berendsen burst.

## Box
- Solvent model: OPC (OPCBOX)
- Geometry: **truncated octahedron** (solvateOct) — minimizes water count vs cubic for a globular monomer (~25% fewer waters), Amber24 §13.6.42 p.263
- Padding: **10 Å** — exceeds the 10 Å nonbonded cutoff is borderline, so I/We set cut=10 Å with 10 Å pad gives ~min-image safety for a compact 58-residue protein that does not unfold; standard buffer for a folded globular stability run (Amber24 §13.6.42 p.263). Conformational drift is minimal (disulfide-locked) so 10 Å is sufficient.
- Ions: 6 Cl⁻ to neutralize net +6 (charge-check tLEaP confirmed +6.000, `system/charge_check2.log`). Neutralize-only via `addIons mol Cl- 0` (Amber24 §13.6.5 p.249).

## Analysis targets
- **Backbone RMSD vs crystal structure** (primary objective) — mass-weighted, backbone @C,CA,N, aligned to minimized crystal reference; time series + mean/SD over converged window
- RMSF per residue (identify flexible regions vs rigid disulfide-locked core)
- Radius of gyration (compactness stability)
- Convergence check on RMSD (plateau, no drift in last 50%)

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable / value |
|------------------------|--------|------------|-----|------------------------|
| Kruchinin et al. 2022, PMID:36499117, DOI:10.3390/ijms232314785 | BPTI 3D hydration | MD (explicit) | AMBER-class | Well-defined hydration layer; buried waters match X-ray |
| Nobili et al. 2023, PMID:37325476, DOI:10.3389/fmolb.2023.1122269 | BPTI stability/folding | metadynamics | atomistic | BPTI a reference small protein for stability since decades |
| Wesołowski et al. 2024, PMID:38512062, DOI:10.1021/acs.jpcb.4c00104 | BPTI folding + SS bonds | QM/SQM/MM | GFN-FF/xTB | SS bonds critical to BPTI structural stability |

BPTI is among the most-studied MD reference proteins; backbone RMSD vs crystal of ~1–2 Å is the established hallmark of a stable folded simulation.

## Method best practices
Standard MD of a folded globular protein — **Step 2c not triggered** (no alchemical/REMD/enhanced-sampling/metal/membrane/nucleic/IDP keyword matches). Plain NPT MD.

## Walltime estimates
| System size | ns/day | This study walltime |
|-------------|--------|---------------------|
| ~13k atoms, 1× GPU (pmemd.cuda) | ~150–300 ns/day (small system) | min+heat+equil ~30–45 min; prod 100 ns ~8–16 h (single GPU); request 96 h walltime, restart/extend if needed |

## Caveats / limitations
- Burst density (Berendsen) cools/heats system slightly — equil2 (MC barostat) warms back to 300 K before production.
- pmemd.cuda may exit 0 with NSTEP<expected during burst if box shrinks fast — equil restart loop handles this.
- Single 100 ns trajectory: stability assessment, not an exhaustive conformational ensemble.
- Protein-only: buffer PO4 and crystallographic waters discarded; fresh OPC solvent (appropriate for an apo stability question).

## Approval: APPROVED 2026-06-09
(Autonomous benchmark run — study prompt specifies the protocol verbatim: 100 ns, explicit water, 300 K, backbone RMSD vs crystal. No interactive user; directive is run-to-completion.)

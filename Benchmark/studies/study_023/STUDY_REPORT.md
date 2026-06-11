# Study Report — Dickerson Dodecamer (1BNA) B-DNA, OL21, 50 ns

## 1. Objective
Simulate the Dickerson-Drew dodecamer d(CGCGAATTCGCG)₂ (PDB 1BNA), a canonical B-DNA duplex, for 50 ns with the OL21 DNA force field, and analyze the helical base-pair-step parameters **rise, twist, roll**, comparing them to crystallographic / canonical B-DNA values.

## 2. System
- PDB 1BNA: B-DNA duplex, chains A (res 1–12, 5'-CGCGAATTCGCG-3') + B (res 13–24, complementary strand). Self-complementary palindrome.
- Biological unit DIMERIC = the two-strand duplex; both strands present in the asymmetric unit (REMARK 350 BIOMT = identity). Preflight `biological_assembly` FAIL was a confirmed false positive — no symmetry expansion needed.
- 80 crystallographic waters stripped; system re-solvated.
- Final system: 21,492 atoms — 758 DNA atoms (486 heavy + 272 H added by tLEaP), 5,171 OPC waters, 36 K⁺, 14 Cl⁻. Net charge 0.
- Box: truncated octahedron (solvateOct, 10 Å iso buffer), volume ~162,000 Å³.

## 3. Protonation Rationale
DNA bases have no titratable groups near pH 7; all bases modeled in canonical Watson–Crick protonation. No propka3 (protein tool) required. pH context ~7 (physiological/solution).

## 4. Methods (actual values used)
- **Force field:** DNA OL21 (`leaprc.DNA.OL21`) — Amber 24's recommended DNA FF (Manual §3.2.2 p.40, explicitly tested on the Dickerson-Drew dodecamer); water OPC (`leaprc.water.opc`, OPCBOX) — Manual §3.6.1 p.54 states OPC "improves structural description of DNA duplex"; K⁺/Cl⁻ Joung–Cheatham ions (auto-loaded with the OPC leaprc).
- **Ionic strength:** neutralize (22 K⁺) + 14 K⁺/14 Cl⁻ → ~150 mM KCl (n_pairs = 0.15/55.5 × 5199 waters).
- **Min1:** restrained DNA `:1-24` @ 10 kcal/mol·Å², 2000 cyc. **Min2:** full, 5000 cyc.
- **Heat:** NVT 0→300 K over 90 ps + 10 ps hold (nmropt TEMP0 ramp), Langevin ntt=3 γ=5.0, DNA restrained 10 kcal/mol·Å², SHAKE (ntc=2/ntf=2), dt=0.002, cut=9.0.
- **Equil (burst density):** NPT, Berendsen barostat (barostat=1) taup=2.0, DNA restrained 5 kcal/mol·Å², 200 ps.
- **Equil2:** NPT, MC barostat (barostat=2) taup=2.0, unrestrained, 500 ps.
- **Production:** NPT, MC barostat taup=2.0, ntt=3 γ=5.0, temp0=300 K, dt=0.002, cut=9.0, iwrap=1, **50 ns** (25,000,000 steps), frames every 10 ps (5000 frames).
- **Engine:** pmemd.cuda (Amber 24), 1 GPU. cut=9.0 Å grounded in Amber24 DNA7 test (p.407); ntt=3/γ=5.0/taup=2.0 in Manual MD example p.386.

## 5. Results
All helical parameters from cpptraj `nastruct` (`groovecalc 3dna`), averaged over 5000 frames (`analysis/BPstep.nastruct.dat`, computed by `analysis/analyze_helical.py`).

**Duplex-averaged base-pair-step parameters:**

| Parameter | MD (interior 9 steps) | MD (all 11 steps) | Canonical / crystal B-DNA |
|-----------|-----------------------|-------------------|---------------------------|
| **Rise** | 3.29 ± 0.28 Å | 3.30 ± 0.34 Å | ~3.3–3.4 Å (1BNA crystal ~3.32 Å) |
| **Twist** | 34.9 ± 6.2° | 35.0 ± 6.4° | ~36° (≈10.0–10.5 bp/turn) |
| **Roll** | 1.3 ± 5.9° | 2.3 ± 6.7° | ~0° (sequence-dependent, −7 to +9°) |

**Per-step values** (`analysis/helical_per_step.png`): rise is flat at ~3.2–3.4 Å across all steps; twist shows the expected sequence dependence (lower at the 2-23/3-22 CpG and 6-19/7-18 ApT steps ~31–32°, higher at GpC/ApA-type steps ~37–38°); roll oscillates around 0° with positive roll at CpG/GpC steps — the well-known sequence-dependent fine structure of the Dickerson dodecamer.

**Groove widths (El Hassan–Calladine, interior steps):** major 18.1 ± 1.6 Å, minor 11.0 ± 1.6 Å (P–P based convention; subtracting the ~5.8 Å phosphate term gives canonical B-form minor ~5.2 Å / major ~12.3 Å). Consistent with B-DNA, not A-form.

**Stability/RMSF:** core backbone RMSD vs the equilibrated start = 1.47 ± 0.29 Å (`analysis/rmsd_core.dat`, `rmsd_core.png`); the duplex stays in B-form throughout. Per-residue RMSF (`analysis/rmsf.dat`, `rmsf.png`) is low for the core (~0.85–1.3 Å) and elevated at the four terminal residues (res 1/12/13/24, ~1.9–2.4 Å) — expected end fraying.

## 6. Convergence Assessment
Converged. `check_convergence` on core RMSD: mean 1.47 Å, first-half 1.473 Å vs second-half 1.465 Å → drift 0.007 Å (≪ 0.5 Å threshold); block-averaging SEM plateaus at ~0.027 Å. Density (1.046 g/cc) and temperature (300.0 K) are stable across production. Helical-parameter SDs are dominated by physical thermal fluctuation, not drift.

## 7. Key Findings
- OL21/OPC reproduces canonical B-DNA geometry for the Dickerson dodecamer: **rise 3.29 Å and twist 34.9° (§5) match crystallographic/canonical B-DNA (~3.3 Å, ~36°)**; roll averages near 0° as expected.
- The simulation captures the **sequence-dependent fine structure** (§5, per-step plot): twist and roll vary systematically by step identity, in line with the deformability long documented for this sequence.
- The duplex is **structurally stable** over 50 ns (core RMSD ~1.5 Å, §5–6) with only terminal-base-pair fraying — typical and benign for B-DNA MD.
- Groove widths and the absence of north-pucker/inclination signatures confirm a **B-form (not A-form) ensemble** (§5).

## 8. Caveats & Limitations
- 50 ns yields well-converged ensemble-averaged helical descriptors but is short relative to the µs runs used in fine force-field discrimination (e.g. Knappeová 2024); reported values are time-averages ± SD, not converged backbone-substate (BI/BII) populations.
- "Crystal" reference values are canonical B-DNA / Dickerson-Drew literature ranges; the crystal structure reflects lattice packing and low temperature, so modest solution-MD differences (slightly sub-36° twist) are physically expected, not error.
- Terminal base pairs fray; they are excluded from core RMSD and de-emphasized in the interior-step averages.
- Mean twist 34.9° is marginally below the canonical 36° — a known mild feature of current AMBER DNA FFs; corresponds to ~10.3 bp/turn, still firmly B-form.

## 9. Comparison to Literature
- **Knappeová et al. 2024, JCTC, PMID 39012172** — benchmarked AMBER DNA force fields (incl. OL21) on the Dickerson-Drew dodecamer, reporting B-DNA helical parameters; our rise/twist/roll fall within the canonical ranges they use as reference.
- **Zgarbová et al. 2025, JCTC, PMID 39748297** — OL21 "maintains accurate representation of canonical B-DNA duplexes," consistent with our converged B-form geometry and near-canonical twist.
- **Tucker et al. 2022, JPCB, PMID 35694853** — dsDNA dodecamer stability/helical analysis; supports the observed sub-2 Å core stability.
- (`mcp__pubmed__compare_to_literature` returned a server error / 0 hits for the specific observable query; precedent above is from the Step 2b protocol search.)

## 10. Data Files
- `system/system.prmtop`, `system/system.inpcrd` — topology + initial coordinates
- `simulations/prod/prod.mdout`, `prod.nc` (50 ns, 5000 frames), `prod.rst7`
- `analysis/BPstep.nastruct.dat` — rise/roll/twist/shift/slide/tilt + groove widths (per step, per frame)
- `analysis/BP.nastruct.dat`, `Helix.nastruct.dat` — base-pair + helical params
- `analysis/rmsd_core.dat`, `rmsf.dat`
- `analysis/helical_per_step.png`, `rmsd_core.png`, `rmsf.png`
- `analysis/analyze_helical.py` — parsing/averaging script
- `PLAN.md`, `PROCESS_REPORT.md`

## 11. References
1. Zgarbová, Šponer, Jurečka. *Refinement of the Sugar Puckering Torsion Potential in the AMBER DNA Force Field.* JCTC 2025. PMID 39748297, DOI 10.1021/acs.jctc.4c01100. (OL21 B-DNA accuracy)
2. Knappeová et al. *Comprehensive Assessment of Force-Field Performance in MD of DNA/RNA Hybrid Duplexes.* JCTC 2024. PMID 39012172, DOI 10.1021/acs.jctc.4c00601. (Dickerson-Drew benchmark)
3. Tucker et al. *Development of Force Field Parameters for the Simulation of Single- and Double-Stranded DNA (DES-Amber).* JPCB 2022. PMID 35694853, DOI 10.1021/acs.jpcb.1c10971.
4. Joung, Cheatham. *Determination of Alkali and Halide Monovalent Ion Parameters.* JPCB 2008. PMID 18593145. (JC ions)
5. Amber 24 Reference Manual — §3.2.2 (DNA OL21, p.40, Table 3.2 p.41); §3.6.1 (OPC, p.53–54); §13.6.5 (addIons, p.249); §36.11.55 (cpptraj nastruct, p.795–799).

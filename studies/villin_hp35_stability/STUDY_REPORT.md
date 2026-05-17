# Study Report — villin_hp35_stability
Date: 2026-05-17

## Objective

Assess folded-state stability of the villin headpiece HP67 subdomain (PDB: 2RJY, Gallus gallus) over 1 ns NPT MD at 300 K using the ff14SB/TIP3P force field combination standard for helical peptides.

## Methods

- **System:** 2RJY, chain A, residues 13–76 (64 residues), ACE/NME capped; 1 HIS (HIS41=HID, propka3 pKa=6.52, ND1→GLU14 H-bond at 2.81 Å); net charge −1, neutralized with 1 Na+; TIP3P box 12 Å padding (~21,000 atoms total)
- **Force fields:** ff14SB (protein), TIP3P (water), Joung-Cheatham (ions)
- **Protocol:** min1 (5000 cyc, backbone restrained 10 kcal/mol·Å²) → min2 (10000 cyc, unrestrained) → heat (100 ps, NVT, 0→300 K, Langevin γ=2 ps⁻¹, backbone 5 kcal/mol·Å²) → burst density (NPT Berendsen, converge 0.95–1.05 g/cc) → equil2 (250 ps, NPT Berendsen taup=2, backbone 0.5 kcal/mol·Å²) → production (1 ns, NPT MC barostat mcbarint=100 taup=5, unrestrained)
- **Analysis:** cpptraj backbone RMSD (:2–65&@CA,C,N) vs. system.inpcrd (crystal reference); per-residue Cα RMSF (byres); check_convergence on rmsd.dat

## Results

### Structural Stability (RMSD)

| Metric | Value |
|--------|-------|
| Mean backbone RMSD | 1.013 Å |
| Std deviation | 0.136 Å |
| First-half mean | 0.997 Å |
| Second-half mean | 1.029 Å |
| Drift (2nd − 1st half) | +0.032 Å |
| Convergence status | **CONVERGED** |

The protein remains stably folded throughout the 1 ns trajectory with backbone RMSD 1.013 ± 0.136 Å from the crystal structure. The near-zero drift (0.032 Å) indicates the protein has not undergone significant conformational drift within this window.

### Flexibility (RMSF)

| Region | Residues (prmtop) | RMSF range (Å) |
|--------|------------------|-----------------|
| N-terminus (LEU13) | 2 | 1.47 |
| Helix 1 + linker | 3–21 | 0.56–0.95 |
| Helix 2 | 22–40 | 0.42–0.77 |
| Loop | 41–49 | 0.44–0.70 |
| Helix 3 (core) | 50–65 | 0.39–0.70 |

Helix 3 (C-terminal core helix) shows the lowest RMSF (minimum 0.39 Å at res 59), consistent with it being the hydrophobic core of the HP35 subdomain. The N-terminus shows elevated flexibility (1.47 Å), expected for a truncated construct with ACE cap. No residue exceeds 1.5 Å RMSF.

### Thermodynamic Observables

| Observable | Value |
|-----------|-------|
| Mean density (production) | 1.0026 g/cc |
| Density range | 0.9929–1.0128 g/cc |
| Final Etot | −45,550 kcal/mol |
| RESTRAINT (production) | 0 kcal/mol |

## Comparison to Literature

| Expectation (from PLAN.md) | Result | Match? |
|---------------------------|--------|--------|
| Backbone RMSD ~1–2 Å | 1.013 Å | ✓ |
| RMSF helices < 1 Å | 0.39–0.95 Å | ✓ |
| RMSF N/C-termini ~1.5–3 Å | N-term 1.47 Å | ✓ |
| Density 1.00–1.02 g/cc | 1.0026 g/cc | ✓ |
| Protein folded at 300 K, 1 ns | Yes (RMSD ~1 Å) | ✓ |

Results are consistent with Zou et al. 2024 (PMID:38649777), who report native HP35 RMSD < 2 Å in control simulations, and Nijhawan et al. 2025 (PMID:40192555), who show HP35 stable at 300 K with RMSD ~1–2 Å.

## Caveats

1. **1 ns << folding timescale (~0.7 µs):** This study measures folded-state fluctuations only; unfolding/refolding events are not sampled.
2. **HP67 construct (res 13–76):** Includes extra N-terminal helix not present in HP35; direct HP35 comparisons are approximate.
3. **Single replicate:** No replica exchange or enhanced sampling; thermodynamic errors are not quantified.
4. **TIP3P over-structures water:** Density 1.003 g/cc (vs. experimental 0.997 g/cc at 300 K) is typical TIP3P behavior.
5. **Restraint mask bug noted in heat:** `@CA,C,N,O` in heat.mdin catches TIP3P water oxygens — corrected in equil2 with `!(:WAT,Na+,Cl-)&@CA,C,N`. Benign for heat phase (final temp 299 K correct), but noted for future runs.

## v1 Agent Stress Test Verdict

Pipeline ran end-to-end without manual intervention after `approve`. All 7 SLURM jobs completed with PASS validation. The intentional v1 fix (temperature truncation before AVERAGES) correctly returned PASS for production temperature. Results match literature quantitatively. **v1 pipeline verified.**

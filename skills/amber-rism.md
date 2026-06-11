# amber-rism.md — 3D-RISM Implicit Solvation Theory

**Use when:** Predicting solvation free energy / solvent structure without explicit-solvent MD. Solves Ornstein-Zernike in 3D → solvent density g(r) + closed-form μ_ex.

**Cost:** ~3-10 sec / single-point on 8 CPU cores. No GPU — CPU-only.

> **No-Hardcoded-Defaults banner (per CLAUDE.md):** Every tunable RISM knob —
> closure (`kh`/`pse1-3`/`hnc`), free-energy functional (`--pc+` / `--gf` / `--uccoeff` → PC+/GF/UC),
> `--buffer`, `--grdspc`, and `--tolerance` — is **study-dependent** and MUST be justified
> per study via the 4-tier protocol (Tier 1 lit precedent → Tier 2 Amber 24 manual via `rag_query`
> → Tier 3 training knowledge, flagged → always validate against the manual). These values are
> set from the solute's size/charge/polarity, NOT copied from the example commands or any prior
> study in this file. Copying a value from a prior study without re-justifying it is banned.

---

## 1. Required inputs

1. **prmtop** — solute (any FF; RISM uses LJ + charges only)
2. **rst7** — solute coordinates (or NetCDF trajectory)
3. **PDB** — atom mapping (`ambpdb -p p -c r > x.pdb`; coords ignored)
4. **.xvv** — bulk-solvent susceptibility from 1D-RISM

### Precomputed .xvv files (cluster paths)

| File | Solvent | Closure | Path |
|------|---------|---------|------|
| `cSPCE_kh.xvv` | cSPCE water | KH | `$AMBERHOME/dat/rism1d/cSPCE/` |
| `cSPCE_pse3.xvv` | cSPCE water | PSE3 | same |
| `cSPCE_hnc.xvv` | cSPCE water | HNC | same |
| `cSPCE_KH_NaCl_0.1M.xvv` | cSPCE + 0.1 M NaCl | KH | same |

**Critical:** closure in rism3d run **must match** .xvv closure. Mismatch → numerical garbage.

For non-standard solvents: precompute .xvv with `rism1d` (manual §7.4).

---

## 2. rism3d.snglpnt

```bash
# EXAMPLE values only — closure / functional / buffer / grdspc / tolerance are
# per-study knobs (see banner). Set each via the 4-tier protocol for YOUR solute;
# do not copy these literals as defaults. The ${VARS} below force a deliberate choice.
rism3d.snglpnt \
  --pdb solute.pdb --prmtop solute.prmtop --rst solute.rst7 \
  --xvv cSPCE_${CLOSURE}.xvv --closure ${CLOSURE} \
  --buffer ${BUFFER} --grdspc ${GRDSPC} --tolerance ${TOLERANCE} ${FUNCTIONAL}
  # CLOSURE   e.g. pse3 (must match the .xvv closure)
  # FUNCTIONAL e.g. --pc+ = PC+/3D-RISM correction (Amber 24 manual §7.2.4 p.120),
  #            corrects non-polar overestimation; --gf (Gaussian Fluctuation) for polar/charged
  # BUFFER e.g. 14.0 / GRDSPC e.g. 0.5,0.5,0.5 / TOLERANCE e.g. 1e-7
  #   — buffer & grdspc scale with solute size/charge (see §6 pitfalls), not fixed
```

For full flag reference → `rag_query("rism3d.snglpnt flags closure buffer grdspc tolerance ng3")`.

### Closure ladder (accuracy ↑ → cost ↑)
- `kh` — fast, robust, less accurate for polar
- `pse1/pse2/pse3` — studies 033/036 found PSE3 worked well for benzene/FreeSolv-type compounds;
  treat as a starting HYPOTHESIS to re-justify per solute, not a default
- `hnc` — most accurate in principle but often fails on charged systems

### Multi-closure chaining (difficult convergence)
```
--closure kh pse2 pse3 --tolerance 1e-3 1e-5 1e-7
```

---

## 3. Key output fields

| Field | Meaning |
|-------|---------|
| `rism_excessChemicalPotentialPCPLUS` | μ_ex via PC+/3D-RISM (`--pc+`) — studies 033/036 found best for benzene; re-justify per solute |
| `rism_excessChemicalPotentialGF` | μ_ex via Gaussian-fluctuation (--gf) |
| `rism_excessChemicalPotentialUC` | μ_ex via Universal Correction (--uccoeff) |

For full output field list → `rag_query("rism3d output functionals list excessChemicalPotential")`.

---

## 4. Trajectory mode

Use `--traj prod.nc` instead of `--rst`. Output writes one block per frame; average μ_ex externally.

---

## 5. SLURM launch

```bash
#SBATCH --partition=defq --ntasks=1 --cpus-per-task=8 --time=02:00:00
# DO NOT set --mem on this cluster (rejects with 1M error)
# DO NOT set --gres=gpu (no GPU build)
module load gnu12/12.2.0 amber/24
source /opt/shared/apps/amber/24/amber.sh

ambpdb -p sol.prmtop -c sol.rst7 > sol.pdb
# CLOSURE / FUNCTIONAL / BUFFER / GRDSPC / TOLERANCE are per-study knobs (see top banner) —
# set each via the 4-tier protocol for this solute; the literals after each are EXAMPLES only.
CLOSURE=pse3          # e.g. pse3 — must match the .xvv closure
FUNCTIONAL=--pc+      # e.g. --pc+ (non-polar) or --gf (polar/charged)
BUFFER=14.0           # e.g. 14.0 — raise for charged/large solutes (§6)
GRDSPC=0.5,0.5,0.5    # e.g. 0.5 — tighten (0.25) for charged solutes (§6)
TOLERANCE=1e-7        # e.g. 1e-7
rism3d.snglpnt --pdb sol.pdb --prmtop sol.prmtop --rst sol.rst7 \
               --xvv cSPCE_${CLOSURE}.xvv --closure ${CLOSURE} \
               --buffer ${BUFFER} --grdspc ${GRDSPC} --tolerance ${TOLERANCE} ${FUNCTIONAL} \
               > rism.out 2>&1
```

---

## 6. Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `closure mismatch with xvv` | --closure ≠ .xvv closure | Use matching cSPCE_${closure}.xvv |
| Job exits code 53 | OOM (large grid) | Reduce buffer/grdspc or add CPUs |
| `Memory specification can not be satisfied` | --mem flag on this cluster | Remove `--mem` |
| Non-polar μ_ex 10-20 kcal/mol too positive | HNC-family overestimates cavity | Add `--pc+` or `--gf` |
| Convergence stalls | Iteration count exhausted | `--maxstep 20000` or closure chaining |
| Charged solute wildly off | Box/grid too small | --buffer ≥ 18, --grdspc 0.25 |

**Note:** the `--buffer`/`--grdspc` literals in the §2 and §5 example blocks (14.0 / 0.5) are sized
for a small neutral solute. They are **size/charge-dependent**, not fixed defaults — for charged or
large solutes raise buffer (≥18) and tighten grdspc (0.25) per this row, justified via the 4-tier protocol.

---

## 7. When 3D-RISM vs alternatives

| Goal | Method |
|------|--------|
| One-shot ΔG_hyd without MD | **3D-RISM** (pick closure+functional per solute — e.g. PSE3+GF was a reasonable starting point in studies 033/036) |
| Endpoint binding ΔG with MD done | **MM-PBSA** or MM/3D-RISM |
| Quantitative absolute ΔG_hyd | **TI explicit-solvent** |
| Solvent g(r) map around binding site | **3D-RISM** (only fast option) |

---

## 8. Validated capability (studies 033 + 036)

GAFF2 benzene single-point:

| Variant | μ_ex (kcal/mol) | vs TI -2.97 |
|---|---|---|
| Raw PSE3 | +12.72 | +15.7 |
| PSE3 + GF | +1.46 | +4.43 |
| KH + PC+ | -3.93 | -0.96 |
| **PSE3 + PC+** | **-2.85** | **+0.12** ← matches TI |

**Studies 033/036 found PSE3 + PC+ best for benzene** (a small non-polar solute): it agreed with explicit TI to 0.12 kcal/mol. Treat this as a starting HYPOTHESIS to re-justify per solute via the 4-tier protocol — do not copy it as a default for other systems. Remaining −2 kcal/mol offset from FreeSolv is GAFF2 dispersion error, not RISM artifact.

- Runtime: ~3.5 sec per closure on 8 CPUs
- KH+PC+ overcorrects for non-polar (PC+ parameterized for PSE family); but for polar solutes KH+PC+ and PSE3+PC+ can both land near experiment (see methanol below)
- **Do NOT assume "GF for polar."** GF *under-solvates* polar solutes (e.g. methanol ΔG_hyd off by ~2 kcal/mol vs experiment) while PC+ matched — mirroring the benzene non-polar result. **Default starting estimator for hydration ΔG = PC+ (or UC), not GF**, re-justified per solute via the tier protocol. Pre-register the estimator you will report BEFORE the run, and pick PC+/UC unless a solute-specific reason favors GF.

---

**References:**
- Amber 24 manual §7 (full RISM chapter)
- Kovalenko & Hirata 1999 *JCP* 110, 10095 — 3D-RISM-KH
- Palmer et al 2010 — UC
- Sergiievskyi et al 2015 — PC+/3D-RISM
- FreeSolv: Mobley & Guthrie 2014 (benzene -0.87 kcal/mol)

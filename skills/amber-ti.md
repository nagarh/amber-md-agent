# Skill: amber-ti — Thermodynamic Integration / Free Energy Perturbation

TI with pmemd.cuda GTI for alchemical free energy calculations (hydration ΔG, relative binding ΔΔG, mutation ΔΔG). Validated studies 012, 016, 108, 115, 118.

---

## GTI Syntax (pmemd.cuda)

```
icfe = 1, ifsc = 1,
timask1 = ':MOL', scmask1 = ':MOL',
timask2 = '', scmask2 = '',
clambda = X, tishake = 0,
scalpha = 0.5, scbeta = 12.0,
```

- **pmemd.cuda GTI** uses `timask1/scmask1` (WITH numeric suffix) — NOT sander syntax (`scmask` no suffix)
- `timask2='', scmask2=''` — empty strings valid in pmemd.cuda
- For VdW annihilation: `scmask1=':MOL'` (softcore all solute atoms)
- For charge annihilation (ifsc=0): needs `timask1/timask2` with SAME atom count (dual topology)
- **Simplest full ΔG_hyd:** combined VdW+charge with ifsc=1 (no dual-topology):
  `icfe=1, ifsc=1, timask1=':MOL', scmask1=':MOL', timask2='', scmask2='', clambda=X`
- **Softcore params `scalpha`/`scbeta`** — the values shown above (`scalpha=0.5, scbeta=12.0`) are the Amber softcore recommendation (Amber 24 manual §21/§24 TI/softcore). NOT fixed — confirm the appropriate softcore settings for your transformation type via `rag_query("TI softcore scalpha scbeta recommended values transformation Amber24")` and justify per study via the tier protocol, mirroring the lambda-window framing below.

---

## Lambda Windows

**RAG-query window placement for your transformation type:**
```
rag_query("TI lambda windows placement softcore solvation mutation convergence")
rag_query("TI FEP lambda spacing accuracy convergence recommended Amber24")
```

Typical starting point (NOT fixed — verify with RAG for your transformation): `0.05, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 0.95`

**Avoid λ=0.30** — crashes on some systems .

> **POLAR / charged solute decoupling — the 0.05–0.95 grid UNDER-ESTIMATES ΔG.** Trapezoid over 0.05…0.95 silently **drops the [0, 0.05] and [0.95, 1] end segments**. For a *non-polar* solute the endpoint dV/dL is small → negligible loss. For a *polar* solute the **electrostatic dV/dL at λ→0 is large** (still rising toward λ=0) → the dropped low-λ segment can be several kcal/mol, badly under-estimating ΔG_hyd. **Fix for polar/charged solutes:** (a) include endpoint windows λ≈0 and λ≈1 (e.g. 0.0, 0.02, … 0.98, 1.0) and/or denser λ near 0; and/or (b) run a **separate decharge leg** (linear λ, no softcore, charges → 0) followed by a vdW-decouple leg (softcore) — ΔG = ΔG_decharge + ΔG_vdW. Do NOT reuse the benzene single-step nonpolar recipe for polar solutes; pair with the ≥500 ps/window guardrail below.

**Minimum 500 ps/window** for convergence (heuristic guardrail — observed in studies 012/016/108/115/118 that 100 ps gives wrong sign; confirm sufficiency per study via `check_convergence` / block-averaging, do NOT treat as a fixed target). At dt=0.001 (required with ifsc=1): nstlim ≥ 500000.

**Small box issue:** Single small molecules (~800 waters) cause pmemd.cuda early exit with "box dimensions changed too much". Use `-AllowSmallBox` flag OR rebuild with larger padding (15+ Å). Without this, each window runs only ~65 ps → wrong ΔG sign.

For smoothstep softcore schedule (alchemical mutations): `gti_lam_sch=1` + see `amber-bugs.md` §TI/Soft-Core for ifsc+ntf=1 trap and ABL1 T315I validation.

---

## Single-Topology Hydration ΔG 

With `timask1=':MOL', timask2=''`: Amber scales INTERMOLECULAR interactions only → vacuum leg = 0.
```
ΔG_hyd = -ΔG_annihilate_water   (for neutral non-polar molecules)
```

**pmemd.cuda cannot run ntb=0** (vacuum). For explicit vacuum leg: use sander.

**GAFF2 benzene accuracy:** -2.97 vs -0.87 kcal/mol experimental = **2.1 kcal/mol systematic error**. GAFF2 overestimates aromatic hydrophobicity. Use RESP charges for publication-quality work.

---

## Relative-binding (single-topology) TI — pmemd.cuda GTI

Required flags (else the run aborts or segfaults):
- minimization needs **`ntmin=2`** (steepest descent) when `ifsc=1`;
- **`timask1`/`timask2` = the whole end-state molecule** (e.g. `:LIG&!@<other-state SC atoms>`), NOT just the unique atoms — masking only the unique atoms segfaults;
- softcore with `noshakemask=':LIG'` **requires `ntf=1`** (else `Softcore requires ntf=1` abort).

**BLOCKER — hand-merged single-topology files explode.** If V0-unique and V1-unique atoms both bond to a shared common atom, the merged topology carries a cross-region bonded term (e.g. an angle spanning both alchemical regions) that this GTI build does NOT auto-exclude → the softcore atoms blow up (runaway temperature and DV/DL). Relative-binding TI here needs a dedicated FE-setup tool (pmemd FEW / BioSimSpace / FESetup) or a proper dual-topology build, NOT a hand-merged prmtop. Note `sander` on this build lacks `icfe` (no TI at all).

---

## SLURM Launch (per-window array)

```bash
#SBATCH --array=0-8
#SBATCH --gres=gpu:1

# Windows from your Step 2c RAG query (see Lambda Windows §) — do NOT hardcode.
# Set --array length to match the number of windows below.
LAMBDAS=(<your_RAG_justified_windows>)
LAM=${LAMBDAS[$SLURM_ARRAY_TASK_ID]}

# Sed lambda into mdin template
sed "s/LAMBDA_VALUE/${LAM}/" ti_template.mdin > ti_${LAM}.mdin

pmemd.cuda -O -i ti_${LAM}.mdin -p system.prmtop -c equil.rst7 \
    -o ti_${LAM}.out -r ti_${LAM}.rst7 -x ti_${LAM}.nc
```

---

## ΔG Integration

Parse `dvdl` from each window's mdout:
```python
import numpy as np

# lambdas: use the SAME list as submitted to SLURM array (from Step 2c RAG query)
# Do NOT hardcode here — read from the actual windows that ran
lambdas = <your_submitted_lambda_list>

dvdl_means = []  # extract from each window's mdout: grep "DV/DL" | average production frames
# Parse: skip an equilibration fraction of each window before averaging DV/DL.
# 20% is a heuristic guardrail — verify per study from the DV/DL time series
# (discard until DV/DL plateaus; rag_query("TI equilibration discard DV/DL convergence") if unsure).
dG = np.trapezoid(dvdl_means, lambdas)  # NumPy 2.0+; use np.trapezoid NOT np.trapz
```

For BAR/MBAR analysis → pymbar (`rag_query("pymbar MBAR TI free energy analysis Amber mdout")`)

---

## Common Pitfalls

| Issue | Fix |
|-------|-----|
| `ifsc=1` + `ntmin=1` (default CG) → crash | Use `ntmin=2` (steepest descent only — Amber 24 manual p.392 §21.6.5; amber-bugs.md §TI Bug 1) |
| `ifsc=1` + `ntf=1` required | ntf=2 masks bond terms needed for softcore |
| λ=0.30 crash | Skip this window |
| 100 ps/window → wrong ΔG sign | Use ≥ 500 ps/window (heuristic guardrail — confirm convergence per study, see Lambda Windows §) |
| `timask` without suffix (sander syntax) in pmemd | Use `timask1`/`scmask1` (GTI suffix) |
| JSON serializer string-quoting C-11 bug | See amber-bugs.md §TI |

---

## References

- GTI: Lee et al. JCTC 2020 (smoothstep)
- GAFF2: Wang et al. JCC 2004
- FreeSolv validation: He et al. JCTC 2025 (PMID:40068154)
- Amber 24 manual §24.4

# amber-sgld.md — Self-Guided Langevin Dynamics (SGLD / SGLDg / SGLD-GLE)

**Use when:** Need enhanced conformational sampling that (a) runs as a single trajectory (no replicas), (b) accelerates low-frequency motion (slow torsions, domain motions), (c) preserves closed-form reweighting back to canonical ensemble. **CV-free** like GaMD but biases momentum/force, not PE.

---

## 1. SGLD variants

For full variant table (isgld, sgft, sgff value ranges) → `rag_query("SGLD isgld sgft sgff variants SGLDg SGLD-GLE")`.

**Choose:**
- `sgft=1.0, sgff=0` — fastest sampling, momentum-only guidance; strongest enhancement but largest reweighting spread (justify per study via tier protocol)
- `sgft=0.5, sgff=-0.1` — combined SGLDg with milder distribution distortion
- `sgfg=1.0` — SGLD-GLE; exactly conserves canonical ensemble (no reweighting needed) but slower convergence
- `isgld=3` — SGLDg balanced; canonical with no reweighting but minimal enhancement

---

## 2. Minimal mdin (vacuum/igb)

> ILLUSTRATIVE EXAMPLE — vacuum alanine dipeptide (aladip). The tunable
> science parameters below (`temp0`, `gamma_ln`, `nstlim`, `tsgavg`, `sgft`,
> and the `ntwx`/`ntpr`/`ntwr` write frequencies) are NOT defaults: each must
> be justified per study via the tier protocol (lit precedent → Amber 24
> manual → training knowledge, then manual validation). `isgld=1` and the
> namelist/flag names are required SGLD syntax and stay fixed.

```
SGLD production aladip
&cntrl
   imin=0, irest=0, ntx=1,
   ntt=3, temp0=300.0, gamma_ln=1.0,
   ntc=2, ntf=2, dt=0.002,
   nstlim=5000000, ntb=0,         ! 10 ns demo run — set length per study (see §3 barrier ceiling)
   igb=6, cut=9999.0,            ! CUDA-GB requires cut > 999
   ntpr=500, ntwx=500, ntwr=50000, ig=-1,   ! dense ntwx/ntpr=500 for SGLD reweighting/PMF sampling (overrides benchmark ntwx=50000)
   isgld=1, tsgavg=0.2, sgft=1.0,
   isgsta=1, isgend=22,           ! atom range to bias (or use sgmask)
/
```

**Critical CUDA quirk**: `igb=6` (vacuum) or any GB on pmemd.cuda **requires** `cut > 999.0`. Default `cut=8.0` fails immediately with: `CUDA (GPU): Implementation does not support the use of a cutoff in GB simulations. Require cut > 999.0d0.` Set `cut=9999.0`.

For explicit-solvent SGLD, use periodic BC + standard cutoff (no special quirk).

---

## 3. Tuning tsgavg

`tsgavg` = low-frequency averaging window (psec).

| `tsgavg` | Enhances | Recommended for |
|---|---|---|
| 0.2 ps (short window) | bond rotations, ψ/φ torsion crossings | secondary structure folding, ligand docking |
| 1.0 ps | slow domain motions | quaternary assembly, allosteric transitions |
| 5-10 ps | very slow large-scale events | rare unfolding/refolding |

**Barrier ceiling (heuristic guardrail):** SGLDg with combined sgft=1.0 + sgff=−0.3 does NOT cross ~5–6 kcal/mol barrier in 10 ns of vacuum aladip (in-house observation, this study's §9 validated run — not a literature-cited limit). For barriers ≥5 kcal/mol: use umbrella, ABMD, or extend to ≥50–100 ns.

---

## 4. Atom selection

- `sgmask=':1-150'` — only solute (typical for solvated systems)
- **Solvent reweighting blow-up:** sgft=1.0 on explicit-solvent gives SGWT spread ~40 kcal/mol (vs 2-5 in vacuum) — solvent slow modes leak into low-frequency band. Effective sample size collapses. For explicit-solvent: use sgft=0.3-0.5, sgmask='solute & heavy', tsgavg=0.5-1.0 ps, ≥20 ns trajectory.

---

## 5. Reweighting

```
weight_i = exp(SGWT_i)
```

Use Amber-bundled scripts:
```
sgldinfo.sh sgld_prod.mdout       # extract SGLD properties
sgldwt.sh   sgld_prod.mdout       # per-frame weights + reweighted averages
```

For mdout column meanings → `rag_query("SGLD mdout output columns SGWT SGFT TEMPSG EPOTLF")`.

---

## 6. SLURM launch (pmemd.cuda)

```bash
#SBATCH --partition=defq --gres=gpu:1 --time=02:00:00
module load gnu12/12.2.0 amber/24
source /opt/shared/apps/amber/24/amber.sh

pmemd.cuda -O -i sgld_prod.mdin -o sgld_prod.mdout \
  -p ../system/sys.prmtop -c ../system/sys.rst7 \
  -r sgld_prod.rst7 -x sgld_prod.nc -inf sgld_prod.mdinfo
```

---

## 7. RXSGLD (replica-exchange variant)

Combine SGLD with REMD by varying `sgft` across replicas. For setup → `rag_query("RXSGLD replica exchange SGLD setup")` + Amber manual §25.3.6.

---

## 8. Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `CUDA (GPU): Implementation does not support the use of a cutoff in GB simulations` | igb≥1 with cut<999 on pmemd.cuda | Set `cut=9999.0` |
| All SGWT ≈ 0 with sgft=1.0 | system at equilibrium / no slow motion | normal at start; increases over 100s of ps |
| Apparent temperature drifts | gamma_ln too low | use gamma_ln=1.0-10.0 ps⁻¹ |
| Reweighted average garbage | sgft too large → weights collapse | reduce sgft to 0.5, or use sgft=0 sgff=-0.1 |
| Solute distorts unphysically | SGLD applied to solvent | use `sgmask=':1-N'` |

---

## 9. Validated capability

Aladip vacuum igb=6, 10 ns, sgft=1.0, tsgavg=0.2 ps, gamma_ln=1.0:
- C7eq/αR @ φ=−72.5° (deepest), C5 @ φ=−147.5° (PMF 0.71)
- αL @ φ≈+60 **not crossed** in 10 ns
- Raw vs reweighted PMF agree within 0.05 kcal/mol
- Wall: 1583 ns/day on pmemd.cuda (negligible SGLD overhead)

---

**References:**
- Amber 24 manual §24.1
- Wu & Brooks 2003 *Chem Phys Lett* 381, 512 — original SGLD
- Wu 2014 *JCTC* — SGMDg/SGLDg
- Wu 2019 — SGLD-GLE
- Wu & Brooks 2020 — RXSGLD

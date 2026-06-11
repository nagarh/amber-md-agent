# amber-abmd.md — Adaptively Biased MD (ABMD / Well-Tempered ABMD)

**Use when:** Constructing free-energy profile along a CV without pre-defining windows (vs umbrella) and without re-weighting from full boost (vs GaMD). ABMD is Amber's *metadynamics-equivalent*: time-dependent biasing potential from kernel deposition that flattens the FES.

**Cost:** Vacuum aladip phi: 10 ns in 410 sec on 1× RTX A6000 (2107 ns/day).

---

## 1. ABMD principles

Amber's ABMD (manual §25.4.5): `infe=1` + `&abmd` namelist. Biasing potential `U_s(s,t)` evolves over time.

**Well-Tempered (WT) ABMD** — deposition rate decreases as U_s grows:
```
F(s) = -(1 + T/T') * U_s(s)
```
T = sim temperature, T' = `wt_temperature`. At T=300 K, T'=5000 K: factor = 1.06. At T'=3000: factor = 1.10.

---

## 2. Input files

### `cv.in` — Collective variable definition

For cv_type options → `rag_query("NFE colvar cv_type options DIHEDRAL DISTANCE ANGLE MULTI_RMSD")`.

Example (phi torsion, aladip atoms 5,7,9,15):
```fortran
&colvar
  cv_type = 'TORSION',
  cv_ni = 4, cv_i = 5, 7, 9, 15,
  cv_min = -3.14159, cv_max = 3.14159,
  resolution = <rag: "NFE colvar resolution grid spacing recommended convergence">
/
```

Multi-CV: stack multiple `&colvar` namelists for 2D-ABMD.

### Production mdin

**RAG-query before setting ABMD parameters:**
```
rag_query("ABMD timescale wt_temperature flooding recommended parameter selection")
rag_query("ABMD infe NFE colvar cv_file format TORSION DISTANCE")
```

**Known issue:** The &abmd namelist REQUIRES `mode = 'FLOODING'` as first field. Missing → "Cannot read &abmd namelist!" FATAL error. The field names below are EXACT — wrong names (e.g., `output_file` instead of `monitor_file`) cause silent ignore.

```fortran
ABMD WT-FLOODING phi torsion
&cntrl
  imin=0, irest=0, ntx=1,
  ntb=0, cut=999.0, rgbmax=999.0, igb=6,    ! Amber 24 manual p.410: GPU GB requires cut>999
  nstlim=<rag: "ABMD nstlim convergence recommended system size">, dt=<rag: "timestep dt SHAKE ntc=2 recommended">,
  ntc=2, ntf=2,
  ntpr=<rag: "ntpr energy log frequency recommended">, ntwx=<rag: "ABMD ntwx trajectory frequency">, ntwr=<rag: "ntwr restart write frequency recommended">,
  ntt=3, gamma_ln=<rag: "Langevin gamma_ln collision frequency recommended">, ig=-1,
  tempi=<rag: "production temperature tempi temp0 recommended">, temp0=<rag: "production temperature tempi temp0 recommended">,
  infe=1,
/
&abmd
  mode = 'FLOODING',          ← REQUIRED first field, exact spelling
  monitor_file = 'abmd.txt',  ← NOT output_file
  monitor_freq = <rag: "ABMD monitor_freq update interval recommended">,
  cv_file = 'cv.in',
  umbrella_file = 'umbrella.nc',
  timescale = <rag: "ABMD timescale ps aggressive smooth recommended">,
  wt_temperature = <rag: "ABMD wt_temperature well-tempered metadynamics recommended">,
  wt_umbrella_file = 'wt_umbrella.nc',
/
```

**Timescale guidance** (from RAG, not defaults): 50 ps (high barriers, aggressive), 200 ps (moderate), 500 ps (smooth landscapes). `wt_temperature`: lower (1000-3000) → more suppression of revisited regions.

---

## 3. SLURM launch

```bash
#SBATCH --partition=defq --gres=gpu:1 --time=02:00:00
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

pmemd.cuda -O -i abmd.mdin -p system.prmtop -c min.rst7 \
           -o abmd.mdout -r abmd.rst7 -x abmd.nc -inf abmd.mdinfo
```

For solvated systems: switch to explicit-PME settings (remove igb, set ntb=1/2, and set the nonbonded `cut` per the tier protocol → `rag_query("PME nonbonded cutoff cut recommended explicit solvent")`).

---

## 4. PMF extraction

Amber ships `nfe-umbrella-slice` (at `/opt/shared/apps/amber/24/bin/`).

**Dump native grid (no -d flag)**:
```bash
nfe-umbrella-slice wt_umbrella.nc > U_wt_phi.dat
```

**WARNING:** `-d` uses strict `<min>:<max>:<npoints>` matching grid dimensionality. Mismatched dimensions → `'unexpected number of dimensions'`. Omit `-d` entirely for full grid.

**PMF in Python**:
```python
import numpy as np
data = np.loadtxt('U_wt_phi.dat')
phi_rad, U_s = data[:, 0], data[:, 1]
# T_REF MUST equal temp0 from the production mdin; T_WT MUST equal the
# &abmd wt_temperature. A mismatch silently corrupts the PMF — read both
# back from the run (e.g. grep temp0/wt_temperature from abmd.mdin) rather
# than hardcoding. Values below are illustrative per-study placeholders only.
T_REF = <temp0 from this run's mdin>   # e.g. matches &cntrl temp0
T_WT  = <wt_temperature from this run's &abmd>
F = -(1.0 + T_REF / T_WT) * U_s
F -= F.min()
```

**Sign verification (MANDATORY — `nfe-umbrella-slice` output sign is NOT guaranteed):** after computing F, confirm the PMF minima coincide with the most-populated bins of the CV trajectory histogram (`abmd.txt` col 2 — where the system dwells = free-energy minima). If the minima from `F = -(1+T_REF/T_WT)*U_s` instead fall at unvisited grid edges (with maxima sitting on the populated states), the slice sign is inverted — use `F = +(1+T_REF/T_WT)*U_s`. Never read ΔG without this minima-vs-histogram cross-check; the correct sign is the one whose minima match where the CV actually spent time.

**Restrict to visited region** (essential — PMF outside is noise floor):
```python
phi_traj = np.loadtxt('abmd.txt')[:, 1]
mask = (np.degrees(phi_rad) >= np.degrees(phi_traj).min()) & \
       (np.degrees(phi_rad) <= np.degrees(phi_traj).max())
```

---

## 5. Common pitfalls

> **A dissociable / unbinding CV needs a boundary wall.** ABMD on an unbinding coordinate without a reflecting wall / flat-bottom restraint at `cv_max` lets the system escape the grid (the CV runs off to large values, the bias flattens, and the PMF is meaningless). Apply an NFE `&pmd anchor_position` wall **inside the infe framework** — an `nmropt &rst` restraint does NOT reliably combine with infe ABMD. Bounded / periodic CVs (e.g. torsions) need no wall.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `nfe-umbrella-slice -d ... unexpected number of dimensions` | -d syntax mismatched grid dim | Omit -d entirely |
| PMF min in unvisited region | Reading bias-potential floor | Mask to visited region |
| Bias never grows | `infe=0` or wrong namelist | Set `infe=1`, &abmd after &cntrl |
| Barrier underestimated | WT convergence insufficient | Run ≥50 ns or lower timescale to 50 ps |
| CV never crosses high barrier | Bias deposition too slow | Seed on other side, lower timescale, or use multi-walker |

---

## 6. When ABMD vs alternatives

ABMD good for: 1D/2D PMF with unknown barriers, real-time adaptive bias, no window pre-definition. For alternatives: umbrella (known CV range, converged PMF fast), GaMD (no CV needed), SMD (nonequilibrium pulling), NEB (PES path, not FE).

---

## 7. Validated capability

Aladip vacuum, ff14SB, phi torsion, 10 ns WT-FLOODING:
- αR @ phi=-104° = +0.96 kcal/mol
- C5/PPII @ phi=-174° = +0.37 (global min)
- Barrier αR → C5: 1.17 kcal/mol
- Runtime: 410 sec / 2107 ns/day
- 10 ns insufficient to cross phi=0 cis-amide barrier into αL

---

**References:**
- Amber 24 manual §25.4.5 (NFE: ABMD + WT-ABMD)
- Amber 24 manual §25.4.2 (`&colvar` definition)
- Babin & Roland 2008 *J. Chem. Phys.* 128, 134101
- Barducci, Bussi, Parrinello 2008 *PRL* 100, 020603

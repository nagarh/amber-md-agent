# amber-smd.md — Steered MD (`jar=1`) + Jarzynski non-equilibrium free energy

**Auto-load trigger:** any SMD / steered MD / unbinding-pull / non-equilibrium work request.

**Use when:** Pulling a ligand out of a binding site, dragging a peptide across a membrane, forcing a torsion through a barrier — anything where you want a free-energy estimate from a non-equilibrium pull. Use this when umbrella sampling isn't practical (RC too anharmonic / too long to seed enough windows).

**Cost:** Cheap per replica (500 ps – few ns), but exponentially-biased estimator → need many replicas (32-100+) for converged ΔG. If umbrella sampling is feasible, prefer it. SMD is best for: scouting an RC, generating umbrella seeds, or qualitative unbinding pathways.

---

## 1. Reaction coordinate choice

Pick a distance or COM-COM distance. Amber `jar=1` ramps `r2 → r2a` linearly in `nstlim` steps.

For COM-COM (most common — e.g., pulling a ligand off a residue):
```
&rst
  iat=-1,-1,
  igr1=<idx1>,<idx2>,<idx3>,0,    ! receptor group (0-terminated)
  igr2=<idxA>,<idxB>,0,            ! ligand group
  r2=<start_dist>, rk2=<k>, r2a=<end_dist>,
  ir6=0, ialtd=0,
/
```

For single atom-atom distance: use `iat=1234,5678` and omit `igr1/igr2`.

**Stiffness `rk2`:** 100–200 kcal/(mol·Å²) is a *starting range* — `<rk2_from_study_plan>`, justify per study via the tier protocol (Tier 1 lit precedent / Tier 2 manual) then tune from the observed σ(W) per the rule in §2. Too soft → ligand lags r2(t), noisy work. Too stiff → unphysical bond-breaking energetics.

---

## 2. Pull velocity — the dominant parameter

```
v_pull = (r2a - r2) / (nstlim · dt) Å/ps  → ×1000 for Å/ns
```

| v_pull (Å/ns) | Regime | Comment |
|---------------|--------|---------|
| > 30 | Far from reversible | Work ≫ ΔG, exponential bias huge |
| 5-30 | Fast SMD | Jarzynski 5-10× too high, σ(W) ≥ 10 kcal/mol |
| 1-5 | Slow SMD | Jarzynski usable with 32-64 reps |
| < 1 | Quasi-equilibrium | Few reps OK; consider umbrella instead |

**Rule:** Compute σ(W) across replicas; if σ > ~10 kcal/mol (Jarzynski-convergence heuristic, cf. Park & Schulten 2004 — see References), pull is too fast OR force constant too soft. Slow down by 4× or stiffen by 4× to drop σ.

---

## 3. Production mdin template (NVT)

```
SMD pull
&cntrl
   imin=0, irest=0, ntx=1, tempi=<temp0_from_study_plan>,  ! cold start if restart lacks velocities — set tempi=temp0
   nstlim=<N>, dt=<dt_from_study_plan>,          ! dt tied to SHAKE below — dt=0.002 ONLY valid with ntc=2/ntf=2; confirm per study
   ntb=1, cut=<cut_from_study_plan>,             ! NVT — never NPT during SMD; cut (e.g. 8–10 Å) tied to FF/water cutoff convention, justify per study
   ntc=2, ntf=2,                                 ! REQUIRED SHAKE pairing — gates the dt choice above
   ntt=3, gamma_ln=<gamma_ln_from_study_plan>, ig=<seed>, temp0=<temp0_from_study_plan>,  ! gamma_ln 1–5 ps⁻¹; over-damping distorts non-equilibrium work — justify per study
   ntpr=500, ntwx=1000, ntwr=10000, ioutfm=1,    ! SMD-specific dense-frame OVERRIDE (see note below) — tied to DUMPFREQ/istep1
   jar=1,
&end
&wt type='DUMPFREQ', istep1=100, &end
&wt type='END', &end
DISANG=smd.RST
DUMPAVE=work.dat
LISTIN=POUT
LISTOUT=POUT
```

**Per-study placeholders (No-Hardcoded-Defaults rule):** `temp0`, `cut`, and `gamma_ln` are tunable science params — justify each in PLAN.md via the 4-tier protocol (Tier 1 lit / Tier 2 manual / Tier 3 training+validate). `dt=0.002` is *gated by* the REQUIRED `ntc=2, ntf=2` SHAKE pairing (do not change that pairing); confirm dt is appropriate for the system per study. `tempi` must equal `temp0` for the cold-start velocity draw.

**Write frequencies (`ntpr=500, ntwx=1000, ntwr=10000`) — intentional benchmark override:** these are *deliberately denser* than the CLAUDE.md benchmark-mode default (`ntwx=50000`). SMD work analysis (Jarzynski / 2nd-cumulant) needs frames closely sampled along the pull, so this is the same sanctioned override pattern CLAUDE.md grants umbrella/PMF runs. `ntwx`/`ntpr` here must stay consistent with the `&wt type='DUMPFREQ', istep1=100` block — that DUMPFREQ/istep1 is what actually controls work.dat sampling density.

**Critical:**
- `DUMPFREQ` block MUST come between `&end` (cntrl) and `END`, NOT inside `&cntrl`. Wrong placement → empty `work.dat`.
- `DUMPAVE` filename ≤ 80 chars (Fortran limit). If your DISANG path is long, `cp` it to working dir as `smd.RST`.
- `irest=0, ntx=1, tempi=300` is mandatory if your initial restart came from `cpptraj trajout … restart` — those restarts have coords but NO velocities.

---

## 4. Replica count and seed strategy

Minimum replicas: 16 (to estimate σ(W)). For converged Jarzynski: 32–100.

Each replica needs:
1. Different `ig` seed (e.g., `100001 + k·7919`)
2. Different initial structure if possible (extract N frames from a converged equilibrium trajectory at non-correlated lag intervals)
3. Same DISANG (jar=1 ramps deterministically)

SLURM array:
```bash
#SBATCH --array=0-31
#SBATCH --gres=gpu:1 --time=02:00:00
K=$(printf "%02d" $SLURM_ARRAY_TASK_ID)
mkdir -p rep_$K && cd rep_$K
cp $STUDY/smd.RST smd.RST   # local copy for 80-char safety
pmemd.cuda -O -i ../mdin_$K.in -p $TOP -c ../frame.rst7.$((SLURM_ARRAY_TASK_ID+1)) \
           -o smd.out -r smd.rst7 -x smd.nc > smd.log 2>&1
```

---

## 5. Analysis — Jarzynski + 2nd cumulant

`work.dat` columns (from Amber `jar=1` spec): `x0(t)  x(t)  force  work`.

```python
import numpy as np
W = np.array([np.loadtxt(f'rep_{k:02d}/work.dat')[:, 3] for k in range(N)])
x0 = np.loadtxt('rep_00/work.dat')[:, 0]

# Discard transient (~20 ps), rezero
W = W[:, n_eq:] - W[:, n_eq:n_eq+1]
x0 = x0[n_eq:]

# Numerically stable Jarzynski: subtract W_min per time-point
R_kcal = 0.001987   # gas constant in kcal/mol/K — physical constant, never changes
temp0 = <temp0_from_study_plan>  # K — from your production mdin temp0, e.g. 300.0
beta = 1.0 / (R_kcal * temp0)
W_min = W.min(axis=0)
dG_jarz = -1/beta * np.log(np.exp(-beta*(W - W_min)).mean(axis=0)) + W_min

# 2nd cumulant (Gaussian approx — verify σ²/2kT << ⟨W⟩ before trusting)
dG_2c = W.mean(axis=0) - W.var(axis=0, ddof=1) / (2/beta)
```

**Validation checks:**
- σ(W) at endpoint should be ≤ ~10 kcal/mol for Jarzynski to converge with 32 reps (convergence heuristic, cf. Park & Schulten 2004 — see References)
- 2nd cumulant valid only if σ²/(2kT) << ⟨W⟩. If σ²/(2kT) ≥ ⟨W⟩ estimator returns garbage (negative ΔG for an obvious positive process).
- Sign convention: ΔG_unbind = +|ΔG_bind|. Compare to MMPBSA after sign-flip.

---

## 6. Common pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `I could not find enough velocities in <file>` | cpptraj-written restart has coords only | `irest=0, ntx=1, tempi=300` to draw Maxwell velocities |
| Empty `work.dat` | DUMPFREQ block missing or inside &cntrl | Move `&wt type='DUMPFREQ', istep1=N` between `&end` and `END` |
| `pull dump filename too long` | DISANG/DUMPAVE path > 80 chars | `cp` files into working dir, refer to bare names |
| Jarzynski ΔG ≫ expt | Pull too fast OR too few reps OR σ too large | Slow pull by 4× OR run 4× more reps |
| 2nd cumulant ΔG hugely negative | Non-Gaussian work distribution | Don't trust 2nd cumulant; trust Jarzynski only |
| Box PBC crossing at end of pull | Ligand exits original cell | Restart from larger box OR reduce r2a |

---

## 7. When to choose SMD vs alternatives

| Method | Best for | Limitation |
|--------|----------|------------|
| **SMD + Jarzynski** | Quick scouting, generating umbrella seeds, hydrophobic unbinding paths | Exponentially biased, needs many reps |
| **Umbrella sampling + WHAM/MBAR** | Production ΔG along a well-defined CV | Need to choose & seed many windows |
| **MMPBSA/MMGBSA** | Endpoint ΔG for ligand binding | Solvation model errors; entropy hard |
| **LiGaMD / Pep-GaMD** | Slow events without predefined CV | Reweighting noise at high boost |
| **TI / FEP** | Relative ΔΔG between similar ligands | Topology engineering required |

---

## 8. Validated capability

Trypsin–benzamidine unbinding, 16 reps × 500 ps, pull 2.9 → 20 Å (17.1 Å over 0.5 ns) ≈ 34.2 Å/ns — in the >30 Å/ns "far from reversible" regime of the §2 table:
- σ(W) = 21 kcal/mol — TOO LARGE, pull too fast
- Jarzynski +43.95 kcal/mol vs experiment +6.5 → method qualitatively correct, quantitatively over by 6×
- 2nd cumulant -293 — non-Gaussian regime, estimator broken
- Confirms gotchas (1), (2), (3) above

---

**References:**
- Amber 24 manual §27.2.6 (NMR restraints with time-varying `r2 → r2a`, `jar=1`)
- Jarzynski 1997 *Phys. Rev. Lett.* 78, 2690 — exponential work average
- Park & Schulten 2004 *J. Chem. Phys.* 120, 5946 — 2nd-cumulant approximation

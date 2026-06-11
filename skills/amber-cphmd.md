# Amber Constant pH MD (cpHMD)

**Trigger:** Need pKa prediction, pH-dependent dynamics, or protonation-state sampling.

## Concept

Constant-pH MD treats protonation state as a Monte Carlo variable: every `ntcnstph` MD steps, attempt a swap of one titratable residue's state. Accept/reject by Metropolis using ΔG_solv + reference state energy (from cpin). Records protonation state in `cpout`.

Output: time series of protonation states → fraction protonated at given pH → Hill fit → pKa.

## Requirements

- **Implicit solvent** — the igb model must match the cpin calibration set and be justified per study via the tier protocol (`rag_query` for cpHMD-calibrated igb); igb=2 and igb=5/8 use different reference energies so the cpin must be regenerated to match. Explicit solvent cpHMD ("discrete") is 5–10× slower
- **Titratable residue types** from `leaprc.constph`:
  - AS4 (Asp, 4 states), GL4 (Glu, 4 states), HIP (His, 3 states: HID/HIE/HIP), LYS (Lys, 2 states), CYS (4 states for free thiol/disulfide), TYR (2 states)
- **cpin file** from `cpinutil.py` — defines which residues titrate, reference energies, state libraries

## Workflow

### 1. Build with constph residues

```
source leaprc.protein.ff14SB    # protein FF: Tier-1/2 candidate — justify per study via the tier protocol & record in PLAN.md; must be compatible with the cpHMD calibration set; ff14SB shown as illustration
source leaprc.constph

# Replace standard Asp/Glu with AS4/GL4 (titratable) in PDB or use sequence
m = sequence { ACE ALA AS4 ALA NME }
saveAmberParm m peptide.prmtop peptide.inpcrd
```

For PDB-loaded systems: rename ASP→AS4, GLU→GL4, HIS→HIP in PDB before loading.

### 2. Generate cpin

```bash
cpinutil.py -p peptide.prmtop -igb 2 -resnames AS4 GL4 HIP -o cpin    # -igb must match the mdin igb and the cpin reference-energy calibration set — justify the igb model per study via the tier protocol; 2 shown as illustration. -resnames AS4 GL4 HIP and other flags are REQUIRED syntax
```

`-resnames` restricts to specific residue types (else titrates ALL eligible). For protein systems with many residues: `-resnames AS4 GL4` titrates carboxylates; `-resnames HIP` adds His.

### 3. mdin for cpHMD

> ILLUSTRATIVE example — every science parameter (igb / temp0 / saltcon / nstlim / ntcnstph / gamma_ln / FF / water / write freqs / solvph) must be re-justified per study via the 4-tier protocol & recorded in PLAN.md. Do NOT copy verbatim. `ntb=0`, `cut=999.0`, `ntc=2`, `ntf=2`, `icnstph=1`, `imin=0`, `irest=1`, `ntx=5` are REQUIRED cpHMD/implicit-solvent syntax — keep as-is.

```
&cntrl
   imin=0, irest=1, ntx=5,                       ! required restart syntax
   nstlim=1000000, dt=0.002,                      ! nstlim: justify per study (PLAN.md)
   ntb=0, cut=999.0, saltcon=0.1,                 ! ntb=0 & cut=999.0 required; saltcon: justify per study
   igb=2,                                         ! igb: must match cpin calibration; justify per study
   ntc=2, ntf=2,                                  ! required (SHAKE)
   ntt=3, gamma_ln=2.0, ig=-1, temp0=300.0,       ! gamma_ln & temp0: justify per study
   ntpr=2500, ntwx=2500, ntwr=50000, ioutfm=1,    ! write freqs: tie to benchmark mode (CLAUDE.md) / cphstats cadence
   icnstph=1,           ! enable cpHMD (required)
   ntcnstph=100,        ! MC attempt every 100 steps = 200 fs; ntcnstph: justify per study
   solvph=4.0,          ! pH for this window; justify per study
&end
```

Write frequencies (`ntpr`/`ntwx=2500`, `ntwr=50000`) follow benchmark-mode storage-conservative defaults (see CLAUDE.md §Benchmark Mode) and must give a `cpout` cadence dense enough for `cphstats` transition counting; raise them if transition statistics are sparse.

### 4. Run with cpin/cpout flags

```bash
pmemd.cuda -O -i prod.in -p peptide.prmtop -c heat.rst7 \
   -o prod.out -r prod.rst7 -x prod.nc \
   -cpin cpin -cpout prod.cpout -cprestrt prod.cprestrt
```

### 5. Multi-pH sampling

Run an array of pH windows spanning the titration. The ±2-unit window around the expected pKa is a sampling heuristic from the cpHMD literature (Mongan 2004 JCC 25:2038) — at >2 units the residue saturates and yields few transitions. Window count and spacing must be justified per study via the tier protocol and recorded in PLAN.md (≈5–7 windows at pH = pKa−2 → pKa+2 is a Tier-1/2 candidate, not a default); increase density near the pKa where the fraction-protonated curve is steepest.

```bash
#SBATCH --array=0-4
PHS=(2.0 3.0 4.0 5.0 6.0)
PH=${PHS[$SLURM_ARRAY_TASK_ID]}
```

Build + cpin generation must complete before any window starts. Use task 0 as build trigger + wait-loop in other tasks.

### 6. Analyze with cphstats

```bash
cphstats -i cpin -O \
    -o calcpka.dat \
    --population pop.dat \
    prod.cpout
```

Per-window output: `Frac Prot`, `Pred pKa = pH - log10(f / (1-f))`, transition count.

### 7. Joint Hill fit

```python
from scipy.optimize import curve_fit
def hill(pH, pKa, n):
    return 1.0 / (1.0 + 10**(n * (pH - pKa)))
popt, pcov = curve_fit(hill, pH_array, frac_prot_array, p0=[4.0, 1.0])
pKa, n = popt
```

Hill n should be ~1.0 for single residue. Deviation indicates coupled titration or poor sampling.

## Pitfalls

1. **Forgetting `-cpin cpin -cpout out.cpout`** — pmemd silently runs as regular MD; no protonation moves
2. **Wrong igb model** — the igb model must match the cpin calibration set and be justified per study via the tier protocol (`rag_query` for cpHMD-calibrated igb). cpin reference energies are igb-specific (e.g. an igb=2 cpin is invalid under igb=5/8); regenerate the cpin to match whatever igb is chosen
3. **ntcnstph too low** — attempts every step is wasteful (most rejected by velocity correlation); too high under-samples
4. **Too few transitions** — at extreme pH (>2 units from pKa), system gets stuck. Use weighted Hill fit or restrict to central windows
5. **Coupled residues** — multiple titrating sites within ~6 Å couple via electrostatics. Hill n ≠ 1, must use multi-site fit
6. **Wrong sequence** — must use AS4 not ASP, GL4 not GLU, HIP not HID/HIE. Standard protonation residues are NOT titratable
7. **AS4 reference energy assumes saltcon match** — change `saltcon` requires careful validation against Mongan ref
8. **Explicit solvent cpHMD** — needs `ntrelax=N` (relax solvent N steps after each accepted MC) + `gb=0` in mdin, plus solvated topology. Much slower; only use when protein conformational ensemble depends on solvent (e.g., loop dynamics around active site)

## Reference benchmark

ACE-ALA-AS4-ALA-NME, igb=2, 2 ns × 5 pH windows:
- pKa = 3.85 ± 0.01 (Hill fit)
- Reference (Mongan 2004 JCC 25:2038): pKa(AS4) = 3.9
- Experimental free Asp: 3.86 – 4.0
- Excellent agreement (-0.05 units from Mongan reference)

## Convergence diagnostic (CHECK BEFORE trusting a protein pKa)

Per residue, inspect the **transition count in each pH window** (cphstats `Transitions` column). A pKa is only trustworthy if the windows *bracketing its midpoint* each show many transitions (≳50–100). If transitions **collapse to single digits at/above the apparent midpoint**, that residue is stuck (kinetically trapped, usually buried/H-bonded) and its fitted pKa is **under-determined — typically under-predicted** for carboxylates.

> Example (HEWL, GB MC-CpHMD): surface residues reproduced experiment well and an *elevated* Glu35 matched, but a buried, Glu35-coupled **Asp52 was under-predicted by ~1.5 units** — its transitions collapsed to single digits in every window above its midpoint. Short single-pH GB sampling cannot converge buried active-site carboxylates.

**Remedies for a flagged buried/coupled residue (justify per study, not a default):** denser windows around its expected pKa; ≥10 ns/window; or pH-REMD (below). Do NOT report its single-pH pKa as converged without these.

## When to extend

- **pHREMD**: replica exchange in pH for better convergence with coupled/buried sites (`-rem 4` in mdin, multi-replica setup) — the first thing to try when the convergence diagnostic above flags a residue.
- **Explicit solvent**: add `ntrelax` (solvent relaxation steps after each accepted MC) and a water box, accept 5–10× slower MD. The water model (TIP3P is compatible with the explicit-solvent cpHMD reference set) and `ntrelax` value (≈100 is a Tier-1/2 candidate) are tunable per study — justify via the tier protocol and record in PLAN.md, not as defaults
- **Coupled cpin**: for multi-residue protein, use `cpinutil.py` without `-resnames` filter to include all titratable
- **Phase-flipping CYS**: with `-resnames CYS`, cpinutil.py adds disulfide-aware titration

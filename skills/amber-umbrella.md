# Skill: Umbrella sampling + MBAR PMF (Amber)

Trigger: User wants free energy along a collective variable (torsion, distance, RMSD) via umbrella sampling, WHAM, or MBAR analysis. Activated for words: "umbrella", "PMF", "potential of mean force", "biased sampling", "WHAM", "MBAR".

Validated on alanine dipeptide φ PMF: 24 windows × 500 ps NVT, MBAR via pymbar, recovers αR/C5/αL basins within literature envelope.

---

## Choosing the collective variable

| CV type | Amber NMR restraint keyword | iat list |
|---|---|---|
| distance | `iat=i,j` | 2 atoms |
| angle | `iat=i,j,k` | 3 atoms |
| torsion / dihedral | `iat=i,j,k,l` | 4 atoms |
| generalized distance (com–com) | `igr1=...,igr2=...` | atom groups (mass-weighted) |

For aladip φ: `iat=5,7,9,15` (ACE-C, ALA-N, ALA-CA, ALA-C).

## Window grid

Rule of thumb: spacing such that adjacent windows overlap by **2–3σ** of unrestrained CV fluctuation (Kästner 2011).

- Aladip φ (small molecule, gas/water): σ ≈ 3°/√k → 15° spacing with k=100 kcal/(mol·rad²) ⇒ overlap ≈ 5σ. Safe.
- Protein–ligand pulling: starting points of 0.5–1.0 Å spacing along distance with k = 5–10 kcal/(mol·Å²) — refine per study (4-tier protocol) so adjacent windows hit the 2–3σ overlap target for the measured CV fluctuation.
- 2-D φ/ψ: grid every 15° in both → 576 windows (expensive but rigorous).

Check overlap **after** running: `⟨CV⟩_k ≈ CV₀_k` and Σ_k N_k with overlap matrix from MBAR diagnostics.

## Restraint syntax (NMR-style)

```
&rst
  iat=5,7,9,15,
  r1=phi0-180, r2=phi0, r3=phi0, r4=phi0+180,
  rk2=100.0, rk3=100.0,              ! production force constant — choose so adjacent windows overlap by 2–3σ of the actual system's CV fluctuation (see Window grid); 100 is the aladip-validation value, not a default
  ir6=0, ialtd=0,
/
```

- `r2 = r3`: harmonic well centered at `phi0`
- `r1`, `r4` set 360° flat-bottom outside, but since `r2=r3` this collapses to pure harmonic
- `rk2`, `rk3` in **kcal/(mol·rad²)** for torsions (Amber converts r values internally from deg→rad)
- For distance restraints, `rk` in kcal/(mol·Å²)
- `ialtd=0`: alternative form disabled (use for unrestrained MD with `nmropt=1` analysis only)

## mdin block

Production (tunable values below are EXAMPLES — justify each per study via the 4-tier protocol; required flags irest/ntx, ntc=2/ntf=2, ntb=1, ntt=3, ig=-1, nmropt=1 must stay as-is):
```
&cntrl
   imin=0, irest=1, ntx=5,
   nstlim=250000, dt=0.002,            ! nstlim = per-window length; set by convergence (run until f_k/PMF stable), not a fixed default
   ntb=1, cut=8.0,                    ! NVT only (small biased systems crash in NPT). cut is FF/water-dependent (8–10 Å) — justify per study
   ntc=2, ntf=2,
   ntt=3, gamma_ln=2.0, ig=-1, temp0=300.0,   ! temp0/gamma_ln are example thermostat settings — justify per study (temp0 from target ensemble, gamma_ln from coupling regime)
   ntpr=500, ntwx=500, ntwr=10000, ioutfm=1,
   nmropt=1,
&end
&wt type='DUMPFREQ', istep1=100, &end    ! REQUIRED — otherwise DUMPAVE silent
&wt type='END', &end
DISANG=restraint.rst                       ! relative path — Fortran 80-char limit
DUMPAVE=phi.dat
```

**Critical gotchas:**

1. **DUMPAVE silent without DUMPFREQ.** No `&wt type='DUMPFREQ', istep1=N` ⇒ no CV samples written. cpptraj extraction from prod.nc is the fallback.
2. **Fortran 80-char filename limit on DISANG.** Long absolute paths trigger `OPNMRG` error. Copy RST file into local workdir and reference relatively.
3. **NPT prod crashes for small biased systems.** Box dimensions change too much. Use NVT for production after density equilibration.
4. **NPT density equilibration must precede production** — run unrestrained NPT until density has converged (monitor the mdout AVERAGES density), then NVT prod with restraint applied. ~100 ps is a per-study starting point (justify via 4-tier protocol), not a fixed minimum — extend if density has not plateaued.

## Window initialization (pre-equilibration — REQUIRED)

**Never start all windows from the same heat.rst7.** Windows far from the equilibrium CV value will spend hundreds of ps drifting to their target — early frames bias the PMF and create poor inter-window overlap. Pre-equilibrate each window with a stiff spring first:

```
# Pre-equil restraint: same geometry as production but a stiffer spring (e.g. ~5× the production k)
# Run NVT from heat.rst7 until the CV reaches phi0 → output preequil.rst7 near phi0
# Then run production from preequil.rst7
```

Pattern: generate both a `preequil.RST` (stiff, a few × the production k) and `prod.RST` (production k from the Window grid 2–3σ overlap rule) per window. Run pre-equil only until the window's CV settles at phi0 — negligible vs production. The stiffness multiple and pre-equil length are starting points; tune per system.

## SLURM array pattern

```bash
#SBATCH --array=0-23
W=$(printf "%02d" $SLURM_ARRAY_TASK_ID)
RST_PROD=$STUDY/rst_files/window_${W}_prod.rst
RST_PREEQUIL=$STUDY/rst_files/window_${W}_preequil.rst

WORKDIR=$STUDY/simulations/win_${W}
mkdir -p $WORKDIR && cd $WORKDIR
cp $RST_PROD restraint.rst
cp $RST_PREEQUIL restraint_preequil.rst

# Step 1 — pre-equilibrate window at its target CV (stiff spring, ~5× production k)
pmemd.cuda -O -i preequil.in -p $STUDY/system/system.prmtop \
    -c heat.rst7 -o preequil.out -r preequil.rst7 -x /dev/null

# Step 2 — production from pre-equilibrated structure
pmemd.cuda -O -i prod.in -p $STUDY/system/system.prmtop \
    -c preequil.rst7 -o prod.out -r prod.rst7 -x prod.nc
```

## MBAR analysis (pymbar 4.0.3)

```python
from pymbar import MBAR, FES
import numpy as np

K = len(phi0_deg)
N_k = np.array([len(s) for s in samples])
N_total = N_k.sum()

# Reduced potential matrix u_kn[l, n] = U_l(x_n) / kT
# For periodic torsion CV with harmonic restraint:
def wrap_180(x): return ((x + 180.0) % 360.0) - 180.0

x_n = np.concatenate(samples)                   # flat sample array (degrees)
u_kn = np.zeros((K, N_total))
for l in range(K):
    dphi_rad = np.deg2rad(wrap_180(x_n - phi0_deg[l]))
    u_kn[l] = K_SPRING * dphi_rad**2 / kT

mbar = MBAR(u_kn, N_k)

# FES on a histogram grid:
fes = FES(u_kn, N_k)
fes.generate_fes(np.zeros(N_total), x_n,        # u_n = 0 → unbiased reference
                 fes_type='histogram',
                 histogram_parameters={'bin_edges': [bins]})
result = fes.get_fes(bin_centers, reference_point='from-lowest',
                     uncertainty_method='analytical')
pmf, dpmf = result['f_i'], result['df_i']
```

**Convergence checks:**

- Per-window ⟨CV⟩ ≈ CV₀ (deviation < 0.3 × spacing — heuristic guardrail)
- σ(CV) per window roughly constant (no stuck or escaped trajectories)
- f_k values stable when changing equilibration cutoff (10% vs 30% discard — heuristic block-analysis check)
- PMF stable when discarding random 25% of frames (heuristic robustness check)

## When NOT to use umbrella

- CV is poorly chosen (system stuck on side reactions) → use REST2/T-REMD
- 2-D or 3-D free energy needed → use 2-D umbrella (expensive) or metadynamics
- Path-CV needed → use string method (PLUMED) or steered MD
- ΔG endpoint binding → use MMPBSA/TI not umbrella unless unbinding profile required

## Common analyses after PMF

- **Reaction barrier:** max PMF − min PMF along path
- **Equilibrium populations:** `p_i = exp(-PMF_i/kT) / Σ exp(-PMF_j/kT)`
- **Compare to GaMD reweighting** (vs GaMD reweighting) — umbrella+MBAR is usually the more reliable estimator for 1-D PMFs; GaMD reweighting can be biased ~1 kcal/mol in shallow basins.

## References

- Kästner 2011, "Umbrella sampling", WIREs Comput Mol Sci
- Shirts & Chodera 2008, JCP — MBAR
- pymbar docs: https://pymbar.readthedocs.io/

## Capability log entry

| Field | Value |
|---|---|
| Skill | `skills/amber-umbrella.md` |
| Date added | |
| Force field | ff14SB — used ONLY in the single aladip validation run; re-justify FF per study via the 4-tier protocol (PLAN.md §Force fields) |
| Solvent | TIP3P — used ONLY in the aladip validation run; re-justify water/ion model per study via the 4-tier protocol |
| Validated CV | torsion (φ) — extensible to distance, angle, COM-COM |

---

## Macromolecular / ligand dissociation PMF → absolute ΔG_bind

A 1-D `COM_DISTANCE` dissociation PMF does **NOT** give a correct absolute binding free energy on its own — for a
charged macromolecular complex it can over-bind several-fold (a raw COM-PMF well of tens of kcal/mol against an
experimental ΔG_bind of order −10). Required practices:

1. **Woo–Roux standard-state framework** — the raw well-depth (W_plateau − W_min) is NOT ΔG°. Add orientational +
   axial + translational restraints on the two partners and apply their analytical free-energy / standard-state-volume
   corrections. Without these, a 1-D COM PMF over-binds badly, especially for charged
   macromolecular interfaces where MM Coulomb dominates and configurational entropy is not recovered.
2. **Scale the umbrella force constant to the LOCAL PMF steepness.** A single weak k across all windows lets windows
   in the steep (short-range electrostatic) region collapse onto each other, leaving an overlap hole (adjacent ⟨CV⟩
   gap exceeding the window spacing). Use larger k /
   denser windows wherever dW/dr is large; confirm ⟨CV⟩_k ≈ center_k and a gap-free overlap histogram before MBAR.
3. **Verify the PMF actually plateaus** — the box must allow separation until W(r) is flat. A PMF still rising at the
   largest sampled separation means the unbound reference was not reached and |ΔG| is unreliable. For charged
   complexes the electrostatic tail is long (Debye length); size
   the box and pull range accordingly, or use a salt concentration that screens it.

**Bottom line:** 1-D COM dissociation PMF is good for the *shape* (well, barrier position, qualitative strength) and
for relative comparisons; it is unreliable for *absolute* macromolecular ΔG_bind without the Woo–Roux corrections.

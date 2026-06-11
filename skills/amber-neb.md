# amber-neb.md — Nudged Elastic Band (NEB) Minimum Energy Path

**Use when:** Finding the *minimum energy path* (MEP) between two known minima. NEB does NOT give free energy — it gives the lowest-energy connector in 3N-dimensional configuration space. Great for: enzymatic transition states (with QM/MM), conformational isomerization, pose-to-pose paths.

**Cost:** Aladip vacuum 100 ps × 8 images = 35 sec on 16 cores.

---

## 1. Input requirements

1. Same `prmtop` for all images
2. Two endpoint `rst7` files (well-minimized)
3. Single `mdin` shared by all images
4. `groupfile`: first N/2 images from endpoint_A.rst7, second N/2 from endpoint_B.rst7
5. `mpirun -np N_total pmemd.MPI -ng N_images -groupfile groupfile`
   - **N_total ≥ 2× N_images** (mandatory per manual)

---

## 2. Production mdin

> **ILLUSTRATIVE example (aladip-vacuum) — re-justify every science parameter per study via the 4-tier protocol & record in PLAN.md. Do NOT copy verbatim.** The tunable values below (nstlim, gamma_ln, skmin/skmax, the &wt anneal schedule, igb, masks, ig) are example choices for the alanine-dipeptide-in-vacuum demo, not defaults. Only the items flagged "required" under **Critical** are fixed by NEB physics.

```fortran
NEB annealing
&cntrl
  imin=0, irest=0, ntx=1,
  ntc=1, ntf=1,
  ntpr=100, ntwx=500, ntwr=5000,
  ntb=0, cut=999.0, rgbmax=999.0, igb=6,   ! ntb=0/cut=999/rgbmax=999 = required non-PBC setup; igb=6 = vacuum — justify implicit model per study (igb 1/2/5/7/8 vs 6)
  nstlim=200000, nscm=0,                   ! nstlim = example; justify per study
  dt=0.0005,
  ig=-1,                                   ! random seed; use a fixed ig (e.g. 42) ONLY for reproducibility tests
  ntt=3, gamma_ln=1000.0,                  ! gamma_ln = example high-friction value; justify per study (see Critical)
  tempi=0.0, temp0=0.0,
  tgtfitmask=":<solute-residues>",         ! e.g. ":1-3" for aladip; must match actual solute, exclude solvent
  tgtrmsmask=":<solute-residues>@N,CA,C",  ! e.g. ":1-3@N,CA,C"; must match actual solute, exclude solvent
  ineb=1,
  skmin=10, skmax=10,                      ! spring constants = example; justify per study (raise skmax 20-50 if images collapse, see §6)
  nmropt=1,
/
&wt type='TEMP0', istep1=0, istep2=10000, value1=0.0, value2=300.0, /        ! anneal schedule = example; justify peak T & step bounds per study
&wt type='TEMP0', istep1=10001, istep2=100000, value1=300.0, value2=300.0, /
&wt type='TEMP0', istep1=100001, istep2=200000, value1=300.0, value2=0.0, /
&wt type='END', /
```

**Critical:**
- `ntc=1, ntf=1` mandatory — SHAKE conflicts with NEB tangent projection
- `dt=0.0005` — NEB instability at 0.002
- `gamma_ln` high friction damps NEB dynamics; `1000.0` follows the Amber 24 manual §24.6 NEB example — Tier-2 candidate, justify per study via the 4-tier protocol and record in PLAN.md (not a default)
- `igb=6` selects vacuum (no implicit solvent); for implicit-solvent NEB justify the GB model per study (igb 1/2/5/7/8). Keep `ntb=0, cut=999.0, rgbmax=999.0` — required non-PBC setup
- `tgtfitmask`/`tgtrmsmask` must select the actual solute residues and must NOT include solvent atoms (diffusion breaks RMS fit)

---

## 3. Groupfile

First N/2 images use endpoint_A.rst7, second N/2 use endpoint_B.rst7. Naming: `mdout.NNN`, `restrt.NNN`, `mdcrd.NNN`.

If intermediates available (crystallography, docked poses), insert between endpoints in path order.

---

## 4. SLURM launch

```bash
#SBATCH --ntasks=16   # 2× N_images
module load openmpi4 amber/24
source /opt/shared/apps/amber/24/amber.sh
mpirun -np 16 pmemd.MPI -ng 8 -groupfile groupfile > neb.log 2>&1
```

GPU: `pmemd.cuda.MPI` with N_GPUs = N_images.

---

## 5. Analysis

Per-image final EPtot from `mdout.NNN`:
```python
import re, numpy as np
energies = []
for k in range(1, N+1):
    with open(f'mdout.{k:03d}') as f:
        last = None
        for line in f:
            m = re.search(r'EPtot\s+=\s+(-?\d+\.\d+)', line)
            if m: last = float(m.group(1))
    energies.append(last)
barrier = max(energies) - min(energies)
```

**Endpoints (images 1, N) print EPtot=0** — no MD runs on them. For absolute reference, do sander single-point on endpoint rst7.

Path geometry via cpptraj on restart files:
```
parm system.prmtop
trajin restrt.001
trajin restrt.002
...
dihedral phi :1@C :2@N :2@CA :2@C
run
```

---

## 6. Common pitfalls

> **CRITICAL — NEB via `pmemd.MPI` is broken on this Amber24 build:** each image exits right after the control-data header, with no dynamics. **Use `sander.MPI` for NEB:** `mpirun -np 2N sander.MPI -ng N -groupfile gf`. Also: `tgtfitmask`/`tgtrmsmask` must be valid atom masks (`@1,2,3,4`, NOT `@1,@2,…`); raise `skmax` to 30–50 if endpoint images collapse onto a neighbour.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Number of CPUs must be a multiple of and at least twice the number of images` | NCPUS < 2 × N_images | Increase `--ntasks` |
| Inner images collapse to one endpoint | Endpoints not well-minimized | Pre-minimize; raise `skmax` to 20-50 |
| Unphysical geometries | dt too large | Use `dt=0.0005, ntc=1, ntf=1` |
| Endpoint EPtot = 0 | Expected | Use sander single-point for absolute energy |
| Solvated NEB diffuses | Solvent in tgtfitmask | Exclude solvent from masks |

---

## 7. Validated capability

Aladip vacuum, ff14SB, 8 images × 100 ps anneal:
- C7eq → C5 MEP via β/PPII basin (TS @ -117, 133)
- Barrier 6.59 kcal/mol (lit: Tobias & Brooks 1992: 4-7)
- Runtime: 35 sec on 16 cores

---

**References:**
- Amber 24 manual §24.6 (NEB ineb=1)
- Mathews & Case 2006 — PNEB in Amber
- Tobias & Brooks 1992 *J. Phys. Chem.* 96, 3864
- Jónsson, Mills, Jacobsen 1998 — original NEB

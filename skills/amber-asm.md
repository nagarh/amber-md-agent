# amber-asm — Adaptive String Method MFEP

Machinery validated. Production tuning per below.

## When to use
- Find Minimum Free Energy Path (MFEP) between two known endpoints in CV space
- Bond-breaking/forming reactions (preferred application, per ASM literature)
- Dihedral transitions: works but needs much longer runs than for bond-distance CVs

When NOT to use:
- 1D PMF along a single CV → use umbrella or ABMD (much simpler)
- Endpoints unknown → use ABMD or GaMD first to find basins, then ASM between them
- Minimum-energy (PES) path → use NEB (faster, no MD)

## Critical implementation notes

### 1. Binary: sander.MPI ONLY
`pmemd.MPI` in Amber 24 SILENTLY exits when asm=1 is in mdin (ExitCode 1, 2 sec, no error). Use `sander.MPI` exclusively for ASM.

### 2. mkdir results/ before mpirun
ASM opens `results/1.dat` ... `results/N.dat` at startup with no fallback. Without pre-existing `results/` directory:
```
Fortran runtime error: Cannot open file 'results/1.dat': No such file or directory
```

### 3. box constraint MANDATORY for dihedral CVs
Without `box = -3.14159, 3.14159` in $COLVAR namelist, dihedral CVs unwrap during path optimization, producing nonsensical paths (raw values > ±π).

## Minimal working setup

### CVs file
```
2
$COLVAR
COLVAR_type = "DIHEDRAL"
atoms = 5, 7, 9, 15
box = -3.14159, 3.14159
$END
$COLVAR
COLVAR_type = "DIHEDRAL"
atoms = 7, 9, 15, 17
box = -3.14159, 3.14159
$END
```

### guess file (2 endpoints, in radians)
```
2
-1.379  1.378
-2.775  2.793
```

### mdin
ILLUSTRATIVE example (aladip) — re-justify every science parameter per study via the 4-tier protocol & record in PLAN.md. Do NOT copy verbatim. The science values below (nstlim, dt, temp0, gamma_ln, and the ntpr/ntwx/ntwr write frequencies) are aladip toy settings, not defaults. REQUIRED syntax (asm=1, &asm namelist keys, -rem 0) must be preserved exactly.
```
ASM aladip MFEP optimization stage
 &cntrl
   imin=0, irest=0, ntx=1,
   nstlim=50000, dt=0.0005,   ! 50K is a toy value — production needs convergence-driven length, justify per study
   ntt=3, temp0=300.0, gamma_ln=5.0,
   ntc=1, ntf=1,
   ntb=0, igb=6, cut=9999.0,
   ntpr=1000, ntwx=1000, ntwr=10000,
   ig=-1,
   asm=1,
 /
 &asm
   dir = "results",
   CV_file = "CVs",
   guess_file = "guess",
   fix_ends = .true.,
 /
```

### groupfile (N groups, first N/2 from reactant, second N/2 from product)
```
-O -i asm_prod.mdin -p system.prmtop -c reactant.rst7 -o asm.0.out -r asm.0.rst7 -x asm.0.nc
... (4 lines from reactant)
-O -i asm_prod.mdin -p system.prmtop -c product.rst7 -o asm.4.out -r asm.4.rst7 -x asm.4.nc
... (4 lines from product)
```

### Launch
```bash
mkdir -p results
mpirun -np 8 sander.MPI -ng 8 -groupfile groupfile -rem 0
```

ASM has its OWN replica exchange, so `-rem 0` (NOT -rem 1 or -rem 3).

## Output files (in dir=results/)

| File | Content |
|------|---------|
| `0.string`, `100.string`, … | Phi/psi (rad, possibly unwrapped) per node per snapshot |
| `convergence.dat` | step / path change metric — monitor for plateau |
| `force_constants.dat` | K_l per node per snapshot |
| `node_positions.dat` | Normalized 0→1 position of each node |
| `exchanges.REX`, `histogram.REX`, `plot.REX` | ASM-internal replica exchange diagnostics |
| `1.dat` … `N.dat` | Per-node CV trajectory |

## Convergence detection

ASM is converged when `convergence.dat` shows a SUSTAINED plateau (not just a single-step low value). The metric<0.1 threshold, the ~5000-step window, and the mean<0.05 check below are heuristic guardrails (not cited Amber/ASM defaults) — tune the plateau criterion per study against your CV scale and record the choice in PLAN.md.

For autonomous detection (output_freq is READ from the actual mdin's ntpr — never assume a fixed value, since the example writes at ntpr=1000 while older notes assumed 100):
```python
import numpy as np

# Derive output_freq from the mdin actually used (ntpr governs convergence.dat rows)
def read_ntpr(mdin_path):
    import re
    with open(mdin_path) as f:
        txt = f.read()
    m = re.search(r"ntpr\s*=\s*(\d+)", txt)
    return int(m.group(1)) if m else 1000

output_freq = read_ntpr("asm_prod.mdin")   # e.g. 1000 for the example mdin above
plateau_steps = 5000                       # heuristic guardrail — re-justify per study
window = max(1, plateau_steps // output_freq)  # rows covering ~plateau_steps of MD

conv = np.loadtxt("results/convergence.dat")
recent = conv[-window:, 1]
if recent.max() < 0.1 and recent.mean() < 0.05:   # heuristic thresholds — re-justify per study
    # converged - write STOP_STRING
    start_step = int(conv[-window, 0])
    end_step = int(conv[-1, 0])
    with open("results/STOP_STRING", "w") as f:
        f.write(f"{start_step}\n{end_step}\n")
```

## Production tuning ()

| Issue | Fix |
|-------|-----|
| Path not converging in 50K steps | Increase nstlim until `convergence.dat` plateaus; bond-distance CVs converge faster than dihedral CVs — justify the chosen length per study (10⁶ steps is a common order-of-magnitude starting point, not a fixed floor) |
| Sparse initial guess (2 points) | Pre-sample with ABMD/umbrella, use multi-point guess |
| Periodic dihedral noise | box constraint per CV, longer runs, smaller dt (0.0005) |
| All structures at endpoints | Pre-equilibrate each node at its intended CV position with restraints before ASM |
| Bouncing convergence metric | Reduce gamma_ln, increase Mav_damp (manual), check force_constant default |

## PMF stage (after MFEP converges)

Once convergence is sustained, write STOP_STRING file with `<plateau_start_step>\n<plateau_end_step>`. ASM averages the path over that interval, defines pathCV, and runs umbrella sampling with Umbrella Integration for PMF.

PMF integration parameters — the values below are the documented ASM/Amber tool defaults (resolution vs sampling tradeoff). Keep the defaults unless your study needs finer/coarser integration; any deviation must be justified per study and recorded in PLAN.md:
- `nbins` (Amber default 100): histogram bins for PMF integration
- `points_per_node` (Amber default 100/N+1): pathCV definition density
- `points_extra` (Amber default points_per_node*5): extrapolation beyond endpoints

PMF stage uses the same groupfile/launch — sander.MPI auto-detects STOP_STRING and switches stages.

## References
- Maragliano & Vanden-Eijnden, Chem Phys Lett 446 (2007) 182 — on-the-fly string method
- Pan et al. JCC 35 (2014) 928 — Amber implementation
- Amber 24 manual §24.7 pages 492-495

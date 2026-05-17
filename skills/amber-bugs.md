# Skill: amber-bugs

Cluster-specific known bugs. Read when encountering errors or before TI / ParmEd / MMPBSA work.

## TI / Soft-Core

### Bug 1 — Minimization with ifsc=1
**Error**: `ERROR: Minimizations with ifsc=1 require the steepest descent algorithm. Set ntmin to 2.`
```
imin=1, ntmin=2, maxcyc=5000,      # correct
imin=1, maxcyc=5000, ncyc=2500,    # WRONG — crashes with ifsc=1
```
Applies to ALL TI minimization mdins (min1, min2).

### Bug 2 — SHAKE with ifsc=1
**Error**: `Softcore potentials require ntf=1 because SHAKE constraints on some bonds might be removed.`
```
ntc=1, ntf=1, dt=0.001,    # correct for all TI equil/prod
ntc=2, ntf=2, dt=0.002,    # WRONG — SHAKE incompatible with ifsc=1
```

### Bug 3 — Quoted float in Fortran namelist
**Error**: `Cannot match namelist object name '0.0'`
```
clambda=0.0,     # correct (bare float)
clambda='0.0',   # WRONG (Fortran reads as string)
```
Also: `timask1`, `timask2`, `scmask1`, `scmask2` must be **inside** `&cntrl`, not after `/`.
The `write-mdin` toolkit may place them incorrectly — always verify generated mdin before submitting TI jobs.

---

## ParmEd (binary broken on this cluster — Python API only)

```python
import parmed as pmd
```

### Structure.copy() fails
Newer ParmEd requires `cls` argument. Load fresh instead:
```python
# WRONG: top.copy()
pmd.load_file(prmtop, inpcrd)   # one call per stripped topology
```

### Slicing gives wrong LJ table
`struct[':RESNAME']` → wrong LJ coefficient table size. Use strip:
```python
# WRONG: keep = struct[':IRE']
struct.strip('!:IRE')   # keep only target residue
```

### tiMerge string quoting bug
`pt.tiMerge(p, ':1-249 :250-498 :82 :331')` → space-containing string treated as one token → wrong atom selections silently.
```python
from parmed.tools.argumentlist import ArgumentList
al = ArgumentList(':1-249 :250-498 :82 :331')
action = pt.tiMerge.__new__(pt.tiMerge)
pt.tiMerge.__init__(action, p, al)   # ArgumentList bypasses quoting bug
action.execute()
```

### tiMerge coordinate mismatch — "nonsoftcore atoms must match" error

**Error:** `TiMergeError: The number of nonsoftcore atoms in mol1mask and mol2mask must be the same.`

Even after verifying atom counts match, tiMerge fails when the COORDINATES of common atoms in mol1 and mol2 differ (e.g. H atoms placed differently by two separate tleap runs).

**Fix:** Sync mol2 common-atom coordinates to mol1 before running parmed:

```python
import parmed, numpy as np

parm = parmed.load_file("combined_raw.prmtop")
parm.load_rst7("combined_raw.inpcrd")
coords = parm.get_coordinates()[0]

# Build (residue_offset, atom_name) → atom_idx maps for mol1 and mol2
# mol1 residues: 0 to N_wt-1 (0-indexed); mol2 residues: N_wt to N_wt+N_ti-1
SC1_NAMES = {'OG1', 'HG1'}           # scmask1 — exclude from sync
SC2_NAMES = {'CG1', 'HG12', ...}     # scmask2 — exclude from sync

mol1_atoms = {}  # (rel_resoffset, atom_name) → atom_idx
mol2_atoms = {}

for res_idx in range(N_wt):
    res = parm.residues[res_idx]
    for a in res.atoms:
        if res_idx == sc_res_idx and a.name in SC1_NAMES: continue
        mol1_atoms[(res_idx, a.name)] = a.idx

for res_idx in range(N_wt, N_wt + N_ti):
    res = parm.residues[res_idx]
    rel = res_idx - N_wt
    for a in res.atoms:
        if rel == sc_res_idx and a.name in SC2_NAMES: continue
        mol2_atoms[(rel, a.name)] = a.idx

# Copy mol1 coords → mol2 for all common atoms
for key, mol2_idx in mol2_atoms.items():
    if key in mol1_atoms:
        coords[mol2_idx] = coords[mol1_atoms[key]]

parm.positions = coords * parmed.unit.angstroms
parm.save("combined_aligned.inpcrd", overwrite=True)
# Then run parmed tiMerge on combined_raw.prmtop + combined_aligned.inpcrd
```

**Why needed:** tleap builds two protein copies independently → H atoms placed at slightly different positions by the AMBER force field minimizer → tiMerge coordinate-matching tolerance (default ~0.1 Å) fails. Forcing identical coords makes tiMerge succeed without tolerance hacks.

---

### TI alchemical endpoint instability (DV/DL divergence)

**Symptom:** λ=0.0 and/or λ=1.0 windows show DV/DL spikes of ±10⁵ kcal/mol. Linear-λ softcore (`scalpha=0.5, scbeta=12.0`) default settings.

**Root cause:** Classic linear-λ softcore has dS/dλ≠0 at endpoints — dummy atoms at λ=0 or λ=1 can overlap active atoms, causing divergent potentials.

**Fix (Amber 24) — smoothstep softcore (Lee 2020, PMID:32672455):**

Add these flags to ALL TI mdin files (equil + prod):

```fortran
gti_lam_sch=1,            ! smoothstep S(λ) — dS/dλ=0 at endpoints → DV/DL=0 at λ=0,1
gti_scale_beta=1,         ! new softcore form (Amber24 manual Eq 25.13)
gti_ele_sc=1, gti_vdw_sc=1, gti_cut_sc=2,
gti_add_sc=1, gti_bat_sc=1, gti_syn_mass=1,
scalpha=0.2, scbeta=50.0, ! defaults under gti_lam_sch=1
gti_vdw_exp=6, gti_ele_exp=2,
```

**Remove/replace:** old `scalpha=0.5, scbeta=12.0` — incompatible defaults.

**Validation:** DV/DL at λ=0.0 and λ=1.0 should be **exactly 0.0000**. If non-zero, smoothstep not active — check flags applied.

**Validated in:** ABL1 T315I + imatinib TI (2026-05-16). v1 with linear-λ: endpoint exclusion required (9 windows, ΔΔG=+1.748 kcal/mol). v2 with smoothstep: full 11 windows (ΔΔG=+1.898 kcal/mol, closer to expt +2.7).

Reference: Amber 24 manual §25.1.7.1, pages 513-515.

---

## MMPBSA.py

### IFBOX flag after stripping
**Error**: `gb>0 is incompatible with periodic boundary conditions`
```python
stripped.strip(':WAT,Na+,Cl-')
stripped.box = None   # REQUIRED — apply to complex, receptor, AND ligand prmtops
stripped.save('com.prmtop', overwrite=True)
```
Reference: `EGFR_erlotinib/strip_topologies.py`

### MMPBSA_mods import error
**Error**: `ModuleNotFoundError: No module named 'MMPBSA_mods'`
```bash
module load amber/24
source /opt/shared/apps/amber/24/amber.sh   # required — module load alone is not enough
```

---

## antechamber

### BCC fails on login node
**Error**: `Fatal Error! Cannot properly run sqm`
Always submit as SLURM job (`--gpus 0`, ~1h walltime). Never run on login node.

### Intermediates write to CWD
Files (ANTECHAMBER_*.AC, sqm.in/out, ATOMTYPE.INF) write to current working directory, not output dir.
Always `cd` into study directory in SLURM script before calling antechamber.

### Crystal PDB → wrong H count
obabel guesses H from distances → wrong count (e.g. 33H instead of 32H).
Never use obabel or antechamber directly on crystal PDB.
Use CCD coord-transplant pipeline in `skills/amber-ligand.md` Branch C:
- CCD provides correct H count from PDB-curated bond orders
- Crystal heavy atom coords preserved exactly (0 Å drift)
- H added geometrically from crystal geometry via RDKit AddHs
Old alignment pipeline (PubChem conformer → rigid body align) retired — produced 3.48 Å RMSD vs crystal.

---

## mdin File Format

### Trailing blank line required
**Error**: `Fortran runtime error: End of file` (in `mdin_ctrl_dat.F90` or `nmr_calls.F90`)
Every Amber mdin file **must** end with a blank line after the closing `/`.
Without it, Fortran reads past EOF regardless of file content.
```
 &cntrl
   imin=0,
   ...
 /
              ← this blank line is mandatory
```
Applies to ALL mdin files: min, heat, equil, prod, TI, REMD, SMD.
When using `write-mdin` or `write-file`, always verify trailing blank line exists.

### `&` character inside restraintmask
**Error**: `Fortran runtime error: End of file` (in `mdin_ctrl_dat.F90`)
The `&` in Amber mask syntax (e.g. `@CA,C,N,O&!:WAT`) is misread as a Fortran namelist group opener inside a quoted string, causing immediate EOF.
```
restraintmask='!:WAT,Na+,Cl-',    # correct — no & inside string
restraintmask='@CA,C,N,O&!:WAT',  # WRONG — & confuses Fortran parser
```
Use `!:RESNAME` (not operator) instead of `&!:RESNAME` (and-not operator) when excluding solvent.

### `@CA,C,N,O` backbone mask restrains TIP3P water oxygens
**Symptom**: Initial RESTRAINT energy ~50,000–80,000 kcal/mol instead of expected ~10–100 kcal/mol. Simulation completes but restraint forces are meaningless — effectively restraining ~7,000 water oxygen atoms.
**Cause**: TIP3P water oxygen atom name is `O`. The mask `@CA,C,N,O` selects ALL atoms named O in the system, including every water oxygen.
```
restraintmask="@CA,C,N,O",   # WRONG — catches ~7000 TIP3P water oxygens
restraintmask="@CA,C,N",      # correct — protein backbone only, no water
```
**Rule**: Always use `@CA,C,N` for backbone restraints. Carbonyl oxygens (`O`) add minimal structural stability; omitting them is standard practice and avoids this bug.

---

## Density / Box Blown Up

### "Periodic box dimensions have changed too much"

**Error**:
```
ERROR: Calculation halted. Periodic box dimensions have changed too much from their initial values.
  Your system density has likely changed by a large amount...
  The GPU code does not automatically reorganize grid cells and thus you
  will need to restart the calculation from the previous restart file.
```

**When it happens**: Any NPT run when box dimensions change faster than PME grid can handle. Most common after fresh solvation (tLEaP builds at ~0.80–0.85 g/cc). GPU pmemd cannot reorganize grid mid-run.

**First: identify which stage crashed**

```
heat crash  → ntb=1 (NVT) → box fixed → this error impossible during NVT heat
              ntb=2 (NPT) → see "Crash during heating" below
equil crash → most common — see burst loop protocol
prod crash  → equil density never converged — rerun equil first
```

**Root cause hierarchy** (check in order):

| Cause | Symptom | Fix |
|-------|---------|-----|
| Fresh solvation (density 0.80–0.85) | Crashes within first 100 steps of first equil | Density burst loop (see below) |
| `taup` too large | Crashes after 1k–10k steps | Reduce `taup=2.0` → `taup=0.5` |
| `barostat=2` (MC) during early equil | Crashes when density far from target | Use `barostat=1` (Berendsen) for ALL equil; MC only for production |
| Production started before equil converged | Crashes in prod | Re-run equil burst loop, validate density in 0.90–1.10 range, then prod |

---

### Crash during heating (ntb=2 NPT heat — wrong but happens)

Heat should always be NVT (`ntb=1`). If someone used `ntb=2` for heat and it crashed:

1. Fix heat.mdin: set `ntb=1` (NVT), remove `ntp`, `barostat`, `taup`, `pres0`
2. Restart heat from last `ntwr` checkpoint: `-c heat_r<N>.rst7` if `ntwr=500` was set, else from min2.rst7
3. After heat completes at NVT, proceed to NPT equil

If heat was correctly NVT but still crashed with this error → system blew up for another reason (bad coordinates, too-large timestep, bad ligand charges). Check:
Read `heat.mdout` with `Read` tool — look for energy spike / NaN before crash. Run `rag-query "energy blow up restart NVT minimization"`.
Fix: run more minimization (increase maxcyc, add stronger restraints), then retry heat.

---

### Crash during equilibration or production — density burst loop

Use `write-equil-density` (flags in CLAUDE.md) — restarts pmemd.cuda in 10 ps bursts until density converges, then re-equilibration before production.

**Step 1** — run `write-equil-density`. Input = last good rst7, usually `heat.rst7`. If crash mid-equil with `ntwr=500` set, use last checkpoint `equil_r<N>.rst7` instead.

**Step 2** — verify burst mdin has trailing blank line (it often doesn't):
```bash
echo "" >> studies/<study>/simulations/equil_density_burst.mdin
tail -3 studies/<study>/simulations/equil_density_burst.mdin | cat -A   # must end with blank $
```

**Step 3** — submit: `python scripts/md_agent.py sbatch studies/<study>/logs/equil_density.sh`

Each burst = 10 ps (5000 steps) at `barostat=1, taup=0.5`. Restarts until BOTH:
- `|mean(last 5 frames) - target_density| <= density_tolerance` (default target=1.00, tol=0.05 → range 0.95–1.05)
- `max(last 5) - min(last 5) < density_fluct_max` (default 0.02 g/cc)

Override with `--target-density`, `--density-tolerance`, `--density-fluct-max`. Typically 3–6 restarts (30–60 ps total).

**Step 4 — CRITICAL — re-equilibrate after density converges**

`write-equil-density` fires production immediately after density threshold. The burst restarts compress the box but do NOT restore temperature — system enters production cold (e.g. 240 K instead of 300 K), skewing all MM-GBSA energetics.

After burst loop completes, always submit a 500 ps re-equilibration before production:

```bash
# equil2.mdin: same as equil.mdin but irest=1, ntx=5, nstlim=250000 (500 ps)
# input: equil.rst7 (burst loop output)
pmemd.cuda -O -i equil2.mdin -o equil2.mdout -p system.prmtop \
  -c equil/equil.rst7 -r equil2.rst7 -x equil2.nc

# Validate before production
python scripts/md_agent.py validate-step equil2.mdout --target-temp 300 --min-density 0.90
# temperature must be ≥ 295 K before proceeding
```

Only after validate-step PASS on temperature → submit production with `-c equil2.rst7`.

**⚠ Constraints for burst mdin** (always apply):
- `barostat=1` (Berendsen) — MC barostat (`barostat=2`) crashes when density far from target
- `taup=0.5` — tight coupling; `taup=2.0` crashes
- `irest=1, ntx=5` — read velocities from previous rst7
- `ntwr=500` — checkpoint frequently; restart from last saved rst7 if one burst crashes

---

## NMR Restraint / DISANG

### Path truncation (Fortran 80-char limit)
**Error**: `Error opening "Old" file from subroutine OPNMRG` (no useful message)
pmemd silently truncates DISANG/DUMPAVE paths > ~80 chars.
```
DISANG=smd_pull.RST        # correct — short relative path
DUMPAVE=smd_com_dist.dat
```
Set `#SBATCH -D <simdir>` and use relative filenames. Never absolute paths for DISANG/DUMPAVE.

---

## tLEaP

### Unassigned loadMol2
Molecule unavailable at runtime if not assigned:
```
MOL = loadMol2 file.mol2   # always assign
```

### NME capping — wrong atom name
Amber NME library uses atom name `C` (not `CH3`) for methyl carbon. Cap PDB must use `C`.

### Relative paths fail with SLURM -D
tLEaP resolves paths relative to its working directory (the SLURM work-dir).
Always use absolute paths in tLEaP scripts:
```python
os.path.abspath(path)   # when writing tLEaP scripts programmatically
```

---

## cap_protein.py

### perpendicular() bug (fixed)
ACE carbonyl oxygen was placed ~0.5 Å from protein N-terminus. Bug fixed in `scripts/cap_protein.py`.
Never recreate from scratch — always use that file.

### HETATM in input → IndexError
MDAnalysis assigns HETATM records to last protein segment → `IndexError: index 0 is out of bounds`.
```bash
grep -E "^ATOM" raw.pdb > protein_only.pdb   # strip HETATM first
python scripts/cap_protein.py protein_only.pdb protein_capped.pdb
```

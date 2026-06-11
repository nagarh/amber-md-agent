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
clambda='0.0',   # WRONG (Fortran reads as string — silent failure or crash)
```

**C-11 note:** `write_mdin` and `write-mdin` (CLI) serialize params as JSON. If you pass a numeric parameter as a Python string (e.g. `clambda="0.0"` instead of `clambda=0.0`), the tool will write `clambda='0.0'` in the mdin file — which Fortran rejects. **Always pass numeric params as float/int, never as string:**

```python
# CORRECT — pass as float
namelist_params = {"clambda": 0.0, "icfe": 1, "ifsc": 1}

# WRONG — passing as string silently corrupts the mdin
namelist_params = {"clambda": "0.0", "icfe": "1"}  # Fortran will reject these
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

**Validated in:** ABL1 T315I + imatinib TI. v1 with linear-λ: endpoint exclusion required (9 windows, ΔΔG=+1.748 kcal/mol). v2 with smoothstep: full 11 windows (ΔΔG=+1.898 kcal/mol, closer to expt +2.7).

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

### RNA prime notation in restraintmask breaks Fortran namelist parser
**Error**: `Fortran runtime error: Cannot match namelist object name o3'c5'c4'c3''`
Atom names with prime notation (O5', O3', C5', C4', C3') contain single quotes. When restraintmask is single-quoted in the namelist, the first prime terminates the string and the rest becomes a namelist variable name.
```fortran
restraintmask='@P,O5',O3',C5',C4',C3'',   ! WRONG — Fortran sees '@P,O5' then ',O3' as variable
restraintmask="@P,O5',O3',C5',C4',C3'",   ! correct — double-quote the string, prime OK inside
```
**Root cause:** `write_mdin` serializes restraintmask with single quotes. Any RNA atom name containing `'` breaks this.
**Fix:** After calling `write_mdin` for any RNA/DNA system with a primed-atom restraintmask, edit the mdin file and replace single quotes around the mask value with double quotes.
Error occurs in `mdin_ctrl_dat.F90` line 1035.

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

Use `mcp__amber__write_equil_density_script(...)` — restarts pmemd.cuda in 10 ps bursts until density converges, then re-equilibration before production.

**Step 1** — call `write_equil_density_script`. Input = last good rst7, usually `heat.rst7`. If crash mid-equil with `ntwr=500` set, use last checkpoint `equil_r<N>.rst7` instead. Required flags (the tool sets these — verify in generated mdin): `barostat=1` (Berendsen), `taup=0.5`, `ntwr=500`, `irest=1`, `ntx=5`.

**Step 2** — verify burst mdin has trailing blank line (it often doesn't):
```bash
echo "" >> studies/<study>/simulations/equil_density_burst.mdin
tail -3 studies/<study>/simulations/equil_density_burst.mdin | cat -A   # must end with blank $
```

**Step 3** — submit: `mcp__amber__submit_slurm(script_path="studies/<study>/logs/equil_density.sh")`

Each burst = 10 ps (5000 steps) at `barostat=1, taup=0.5`. Restarts until BOTH:
- `|mean(last 5 frames) - target_density| <= density_tolerance` (default target=1.00, tol=0.05 → range 0.95–1.05)
- `max(last 5) - min(last 5) < density_fluct_max` (default 0.02 g/cc)

Override with `--target-density`, `--density-tolerance`, `--density-fluct-max`. Typically 3–6 restarts (30–60 ps total).

**Step 4 — CRITICAL — re-equilibrate after density converges**

`write-equil-density` fires production immediately after density threshold. The burst restarts compress the box but do NOT restore temperature — system enters production cold (e.g. 240 K instead of 300 K), skewing all MM-GBSA energetics.

After burst loop completes, always submit a re-equilibration before production.
Length is per-study (see `skills/templates/PLAN.md` §Production length + Equil2 sizing — no default):

```bash
# equil2.mdin: same as equil.mdin but irest=1, ntx=5, nstlim=<from PLAN.md>
# input: equil.rst7 (burst loop output)
pmemd.cuda -O -i equil2.mdin -o equil2.mdout -p system.prmtop \
  -c equil/equil.rst7 -r equil2.rst7 -x equil2.nc

# Validate before production
mcp__amber__validate_step(mdout_file="equil2.mdout", target_temp=<T_from_PLAN>, min_density=<ρ_min_from_PLAN>)
# temperature must be within <tol> K of target before proceeding
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

## ParmEd add12_6_4 — GAFF2 atom types missing from polfile

**Error:** `LJ12_6_4Error: Could not find parameters for ATOM_TYPE c5` (or ns, nv, nz…)
**Cause:** `lj_1264_pol.dat` only covers protein FF atom types. Mixed protein+GAFF2 ligand+metal systems crash.
**Fix:** See `amber-metal_complex.md` §Mixed System — ZAFF (primary) or extended polfile (fallback).

---

## cap_protein (mcp__amber__cap_protein)

### perpendicular() bug (fixed)
ACE carbonyl oxygen was placed ~0.5 Å from protein N-terminus. Bug fixed in `scripts/cap_protein.py`
(wrapped as `mcp__amber__cap_protein`). Never recreate from scratch — always use this tool.

### HETATM in input → IndexError
MDAnalysis assigns HETATM records to last protein segment → `IndexError: index 0 is out of bounds`.
```bash
grep -E "^ATOM" raw.pdb > protein_only.pdb   # strip HETATM first
```
Then: `mcp__amber__cap_protein(input_pdb="protein_only.pdb", output_pdb="protein_capped.pdb")`

---

## cpptraj

### `rmsd backbone` — "backbone" is a reserved atom keyword
**Error:** Empty RMSD dataset ("Set 'backbone' contains no data").
`rmsd backbone :1-76 @CA,C,N` — cpptraj parses "backbone" as a predefined atom selection (selects all backbone atoms), NOT a dataset name.
```
rmsd V001_rmsd :1-76@CA,C,N first out rmsd.dat    # correct
rmsd backbone :1-76 @CA,C,N first out rmsd.dat    # WRONG — 'backbone' is a keyword
```
Same issue applies to other reserved cpptraj keywords: `heavy`, `nohy`, `sidechain`.

### `nastruct output <file>` — invalid argument
**Error:** `Error: [nastruct] Not all arguments handled: [ filename.dat ]`
Use `naout <prefix>` not `output <filename>`. Output files: `BP.<prefix>`, `BPstep.<prefix>`, `Helix.<prefix>`.
```
nastruct noheader naout helical      # correct
nastruct noheader output helical.dat # WRONG — "output" not a valid nastruct argument
```

### `distance :mask1 :mask2 mindist` — invalid argument  
**Error:** `Error: [distance] Not all arguments handled: [ mindist ]`
The `distance` action computes center-of-mass distance, not minimum distance. `mindist` is not a valid argument.
For minimum distance: use `nativecontacts` action or compute multiple individual pairwise distances.

### `box out <file>` — produces no output
`box out file.dat` runs without error but creates no output file. Use cpptraj topology inspection or coordinate analysis to get box dimensions.

---

## pmemd.cuda — Small Box

### "Small box detected" (≤ 2 cells in any dimension)
**Error:** `gpu_neighbor_list_setup :: Small box detected... The current GPU code has been deemed unsafe`
Occurs when box_dimension / cut < ~3. For small molecule systems (~800 waters, 30 Å box, cut=10 Å).
**Fix:** Add `-AllowSmallBox` flag to pmemd.cuda command.
Note: for TI windows, this also causes early exit (NSTEP < expected) — use `-AllowSmallBox` in groupfile lines.

### "Periodic box dimensions have changed too much" during TI
Same box change issue but for small molecule TI windows. Without `-AllowSmallBox`, windows exit at ~65 ps instead of 500 ps target, giving insufficient statistics.

---

## REMD / REST2

### pmemd.cuda.MPI H-REMD exits silently without `-rem 3`
**Symptom:** All output files created (0 bytes), exit code 1, rest2.log shows "4 processors / 4 groups" then nothing.
**Fix:** `-rem 3` is REQUIRED for Hamiltonian REMD (REST2). Add to mpirun command:
```bash
mpirun -np N pmemd.cuda.MPI -ng N -rem 3 -groupfile groupfile
```
Without `-rem 3`, same behavior as running without REMD — each replica starts but exchanges never happen.

### T-REMD requires `irest=0` for each replica
**Symptom:** T-REMD starts, shows "N processors / N groups", then all replicas exit silently with 0-byte output.
**Root cause:** Using `irest=1, ntx=5` reads velocities from a single equilibration restart at T=300K. Replicas at 400-600K start with 300K velocities → immediately unstable.
**Fix:** Each T-REMD replica mdin must use:
```
irest=0, ntx=1, tempi=<replica_temperature>, temp0=<replica_temperature>
```
This draws fresh Maxwell velocities at the correct temperature for each replica.

---

## validate_step — Density reads RMS FLUCTUATIONS, not AVERAGES

**Symptom:** validate_step reports density ~0.02 g/cc and FAIL for an NPT run that actually converged.
**Root cause:** The tool greps for the LAST "Density =" occurrence in mdout. Amber mdout has an "RMS FLUCTUATIONS" section at the end — its "Density" entry is the STANDARD DEVIATION (~0.02), not the average (~1.00).
**Workaround:** Ignore validate_step density FAIL if NSTEP and temperature both PASS. Manually check actual density by reading the second-to-last "Density =" entry (from the last NSTEP block, not RMS section).
```bash
grep "Density" prod.mdout | tail -5  # last few: one will be RMS section, others are actual
```

---

## MMPBSA.py — `idecomp` wrong namelist

**Error:** `InputError: Unknown variable idecomp in &gb`
`idecomp` belongs in `&decomp` namelist, NOT `&gb`. Also requires `-do` flag for decomposition output.
```
&gb
  igb=2, saltcon=0.15,
/
&decomp
  idecomp=2,
  print_res="all",
/
```
Command: `MMPBSA.py ... -do DECOMP_OUTPUT.dat`

---

## numpy — trapz removed in NumPy 2.0

**Error:** `AttributeError: module numpy has no attribute 'trapz'`
`np.trapz()` was removed in NumPy 2.0. Use `np.trapezoid()` instead.
```python
dG = np.trapezoid(dvdl_means, lambdas)   # NumPy 2.0+
dG = np.trapz(dvdl_means, lambdas)       # REMOVED — NumPy 2.0 breaks this
```

---

## packmol-memgen

### `--lipids LIPID:N` KeyError
**Error:** `KeyError: 'N'` (where N is a number)
Colon notation means lipid MIXTURE, not lipid count. `--lipids POPC:36` is parsed as POPC and 36 as two lipid types.
**Fix:** Use `--distxy_fix <Å>` to set box XY size. Number of lipids is auto-determined.
```bash
packmol-memgen --lipids POPC --distxy_fix 60   # correct: ~36 lipids in 60x60 Å
packmol-memgen --lipids POPC:36                # WRONG: KeyError '36'
```

### No CRYST1 → box not set in tLEaP
packmol-memgen output PDB has no CRYST1 record. tLEaP creates inpcrd without box → pmemd crashes at step 0 with "Box parameters not found" or atoms wrapping to ±360,000 Å.
**Fix:** Always `set mol box { X Y Z }` in tLEaP after `loadPdb`. Measure box from atom coordinate extent + 5 Å buffer. Then autoimage the centered.inpcrd before MD (see `amber-membrane.md`).

---

## ABMD — &abmd namelist field names

**Error:** `NFE-Error: Cannot read &abmd namelist!`
Missing `mode = 'FLOODING'` as FIRST field, OR wrong field names.
Required fields (exact names):
- `mode = 'FLOODING'`
- `monitor_file = 'file.txt'` (NOT `output_file`)
- `umbrella_file = 'file.nc'`
- `timescale = N.0`
- `wt_temperature = N.0`
- `wt_umbrella_file = 'file.nc'`
- `cv_file = 'path/to/cv.in'` — use absolute path to avoid Fortran path length issues

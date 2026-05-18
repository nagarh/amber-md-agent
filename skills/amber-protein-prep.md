# Skill: amber-protein-prep

Full protein system preparation pipeline. Covers preflight → cleaning → capping → tLEaP → validation.

## Step 1 — Fetch & Validate Structure

**If user provided PDB ID:** `fetch_pdb(pdb_id="<PDB_ID>")` → skip to Step 2.

**If protein name only:** Run full selection loop (see `amber-mcp.md` Structure Selection Loop):
1. `pdb.search_pdb(target, organism)` → ranked by resolution, filter < 3.0 Å
2. For each: fetch → preflight → chain break?
   - No break → quality gate (resolution < 2.5 Å, clashscore < 20, Ramachandran < 2%)
   - Pass → use this structure ✓
   - Fail → try next intact structure
3. All intact structures fail quality → pick highest resolution intact → warn user → confirm
4. All structures have breaks → pick minimum breaks → run loop modeling:
   ```bash
   python scripts/loop_model.py \
     --pdb studies/<study>/raw_pdbs/<pdb_id>.pdb \
     --missing <A:86-91,A:120-125> \
     --uniprot <ID> \
     --out studies/<study>/raw_pdbs/<pdb_id>_modeled.pdb
   ```
   Script handles: AlphaFold → pLDDT check → graft if > 70 → ESMFold if not in DB → ask user if pLDDT < 70 or AA > 400

**Log in PROCESS_REPORT:** PDB selected, resolution, quality gate results, any modeled residues + pLDDT values, all user decisions.

## Step 2 — Inspect & Clean

```
inspect_pdb(pdb_file="<raw.pdb>")
clean_pdb(pdb_file="<raw.pdb>", output_file="clean.pdb")   # runs pdb4amber
```

## Step 3 — Preflight (MANDATORY)

```
preflight(pdb_file="<clean.pdb>")
```

Fix ALL flagged issues before writing tLEaP scripts:

| Flag | Fix |
|------|-----|
| Ligand no H | `skills/amber-ligand.md` pipeline |
| Truncated termini | Cap with ACE/NME (see below) |
| Modified residues (TPO/SEP/PTR) | parmed conversion |
| Disulfides | note for tLEaP `bond` commands |
| Mid-chain break (any position) | FAIL — find PDB without break first; if ≤400 AA use ESMFold public API; if >400 AA ask user |
| Close contacts | minimization will fix |

## Step 3a — Protonation States (MANDATORY — run propka3 first)

**Always run propka3 before tLEaP.** propka3 is available in PATH (`/home/hn533621/.local/bin/propka3`, v3.5.1) — runs as Python script on login node (not an Amber tool, no SLURM needed).

### Run propka3
```bash
# propka3 is a Python tool — runs on login node (not Amber binary)
# Use amber_development env which has propka3 3.5.1 installed
/home/hn533621/.conda/envs/amber_development/bin/propka3 -o 7.0 studies/<study>/system/protein_only.pdb
# Output: protein_only.pka
```

### Read propka3 output
The `.pka` file has a SUMMARY OF THIS PREDICTION section:
```
SUMMARY OF THIS PREDICTION
     Residue       pKa  model pKa  ligand  ...
     HIS  57 A    6.43      6.50         ← pKa < 7 → protonated (HIP)
     HIS 119 A    8.12      6.50         ← pKa > 7 → neutral HID/HIE
     ASP  52 A    4.01      3.80         ← pKa < 7 → deprotonated (ASP) ✓
     ASP 102 A    9.23      3.80         ← pKa > 7 → protonated (ASH!)
     GLU  35 A    5.89      4.50         ← pKa < 7 → deprotonated (GLU) ✓
     LYS 210 A   10.53     10.50         ← standard, stay LYS
```

### Decision rules from pKa at pH 7.0
| Residue | propka pKa vs 7 | Assignment | Note |
|---------|----------------|------------|------|
| HIS | pKa < 6.0 | HIP (charged +1) | protonated at pH 7 |
| HIS | 6.0 ≤ pKa ≤ 8.0 | HID or HIE | neutral; check H-bond network |
| HIS | pKa > 8.0 | HID (default) | strongly deprotonated |
| ASP | pKa > 7 | ASH | buried — protonated |
| GLU | pKa > 7 | GLH | buried — protonated |
| CYS | pKa < 7 | deprotonated CYM | check for disulfide first |

For HIS in the 6–8 range: inspect H-bond network. Metal coordination → HID. H-bond donor to nearby acceptor → HIE. Otherwise → HID.

### Apply non-standard protonation in PDB before tLEaP
```bash
# Rename selectively by residue number — do NOT use global sed
# Example: rename HIS 57 to HIP
/home/hn533621/.conda/envs/amber_development/bin/python -c "
lines = open('protein.pdb').readlines()
out = []
for l in lines:
    if l[:4] == 'ATOM' and l[17:20].strip() == 'HIS' and l[22:26].strip() == '57':
        l = l[:17] + 'HIP' + l[20:]
    out.append(l)
open('protein_protonated.pdb','w').writelines(out)
"
```
Always log all non-default protonation assignments in PLAN.md §"Protonation states" with propka pKa as rationale.

### ASP / GLU protonation
Default: deprotonated (ASP, GLU) at pH 7. Only flag ASH/GLH when propka3 pKa > 7 AND residue is buried (no bulk-solvent access).

## Step 4 — Terminal Capping

Determine construct type before running tLEaP:

| Construct | N-terminus | C-terminus | Detection |
|-----------|-----------|-----------|-----------|
| Full-length | none (NH3+) | none (COO-) | First residue number = 1 |
| Truncated domain | ACE | NME | First residue number ≠ 1 |

Uncapped truncated termini carry unphysical ±1 charges — distorts electrostatics, affects ion placement.

```bash
# Strip HETATM first — cap_protein.py crashes on ligand records
grep -E "^ATOM" raw.pdb > protein_only.pdb
python scripts/cap_protein.py protein_only.pdb protein_capped.pdb
```

⚠ Always use `scripts/cap_protein.py` — never recreate from scratch (`perpendicular()` bug was fixed there)
⚠ NME: Amber library uses atom name `C` (not `CH3`) for methyl carbon — cap PDB must match

## Step 5 — Write tLEaP Script

```
write_tleap(output_path="tleap.in", commands="cmd1; cmd2; ...")
```

**Always use absolute paths** in all tLEaP commands — relative paths fail when SLURM sets `-D` to a subdirectory:
```python
os.path.abspath(path)   # use when writing tLEaP scripts programmatically
```

Typical tLEaP sequence — **FF/water/ion names from PLAN.md §Force fields, NOT hardcoded here**:
```
# Replace <PROTEIN_FF>, <WATER>, <WATER_UPPER>BOX, <ION>, <PADDING> with values
# selected in PLAN.md Step 4 §Force fields (per Tier 1/2/3 protocol in amber-workflow.md).
# Do not paste this block with literal ff14SB/tip3p — agent must substitute per study.

source leaprc.protein.<PROTEIN_FF>            # e.g. ff19SB, ff14SB, a99SB-disp
source leaprc.water.<WATER>                   # e.g. opc, tip3p, tip4pew, spceb
loadAmberParams /abs/path/to/ligand.frcmod
MOL = loadMol2 /abs/path/to/ligand.mol2
prot = loadPdb /abs/path/to/protein_capped.pdb
sys = combine {prot MOL}
addIons sys <CATION> 0                        # e.g. Na+, K+
addIons sys <ANION> 0                         # e.g. Cl-
solvateBox sys <WATER_UPPER>BOX <PADDING>     # e.g. OPCBOX 12.0 (water keyword from PLAN)
saveAmberParm sys /abs/path/to/system.prmtop /abs/path/to/system.inpcrd
quit
```

**Common mismatch trap:** `leaprc.water.<X>` loads BOTH the water model AND the
Joung-Cheatham ion params tuned for that water. If you `source leaprc.water.opc`
the ions will be JC-OPC variants, not JC-TIP3P. Mixing leaprc.water.tip3p with
manually-loaded opc params → wrong ion behavior. Always use the leaprc that
matches your PLAN.md water choice.

### Ion concentration
Default — always use neutralize-only:
```
addIons sys Na+ 0    # adds enough Na+ to reach net charge = 0
addIons sys Cl- 0    # adds enough Cl- to reach net charge = 0
```
`0` = "add as many as needed to neutralize." Both lines together handles both positive and negative net charges. This is standard for binding studies and free energy calculations — adding extra salt changes the reference state.

Only add physiological salt (150 mM NaCl) when user explicitly requests it or study specifically requires physiological ionic strength (DNA, highly charged proteins, ion-specific effects).

### Box size
| Padding | When |
|---------|------|
| 10 Å | Small peptides < 50 residues, compute time critical |
| 12 Å | Standard — most protein-ligand binding studies |
| 15 Å | Highly charged protein (net charge > ±10), large conformational changes, IDPs |

Rule: box side must be > protein diameter + 2× padding AND > 2× PME cutoff (20 Å for cutoff=10). Check box dimensions after tLEaP: `inspect_pdb(pdb_file="system.prmtop")`.

### Multimer / oligomer systems
Load full multimer PDB (preferred — preserves inter-chain contacts):
```
sys = loadPdb /abs/path/to/dimer.pdb   # requires TER cards between chains
```
Or combine chains separately:
```
chainA = loadPdb /abs/path/to/chainA.pdb
chainB = loadPdb /abs/path/to/chainB.pdb
sys = combine {chainA chainB}
```
Inter-chain disulfides — use absolute residue numbers:
```
bond sys.82.SG sys.331.SG   # chain A Cys82 — chain B Cys331
```
`addIons` neutralizes whole complex charge. RMSD masks per chain: `@CA&:1-249` (chain A) vs `@CA&:250-498` (chain B).

## Step 6 — Run tLEaP (via SLURM — never on login node)

```
write_slurm(
  output_path="studies/<study>/system/run_tleap.sh",
  commands="cd /abs/path/studies/<study>/system && tleap -f tleap.in > tleap.log 2>&1",
  job_name="tleap_<study>",
  work_dir="/abs/path/studies/<study>/system",
  gpus=0,
  walltime="00:30:00"
)
submit_slurm(script_path="studies/<study>/system/run_tleap.sh")
```

Poll until done, then read `tleap.log` for validation.

## Step 7 — Validate tLEaP Output (MANDATORY)

```
validate_tleap(log_file="studies/<study>/system/tleap.log")
```

| Status | Indicator |
|--------|-----------|
| ✓ Required | `Exiting LEaP: Errors = 0` |
| ✗ Stop | `Errors = N` (N > 0) |
| ✗ Stop | `Could not open file` |
| ✗ Stop | `Could not find atom type` |
| ✗ Stop | `Could not find bond parameter` |
| ✗ Stop | `Fatal Error` |
| ✗ Stop | Missing heavy atoms |
| ✗ Stop | Non-integer net charge |
| ○ Benign | Terminal name formatting warnings |
| ○ Benign | `addIons: same sign` when charge ≈ 0 |

If ligand bond warnings → ligand coordinates wrong → redo `amber-ligand.md` alignment step.
If FAIL → diagnose, fix tLEaP script, re-run. Do NOT proceed to simulation.

## Step 8 — Verify Output Files

```bash
ls -lh system.prmtop system.inpcrd   # both must exist, non-zero size
```
Then `inspect_pdb(pdb_file="system.prmtop")`.

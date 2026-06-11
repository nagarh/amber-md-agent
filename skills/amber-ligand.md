# Skill: amber-ligand

Full ligand preparation pipeline. Use for any ligand parametrization task.

## Decision Tree

```
Ligand input?
│
├── User file WITH H (mol2/SDF/PDB with H atoms present)
│     → Step A: preflight completeness check
│     → Step B: antechamber directly
│
├── User file WITHOUT H (mol2/SDF, bond orders correct, no H)
│     → Step A: RDKit AddHs
│     → Step B: antechamber
│
├── Crystal HETATM (no H) ← most common case
│     → Step 1: extract HETATM (one chain only) — crystal coords preserved exactly
│     → Step 2: SMARTS at study pH → set formal charges on heavy atoms
│     → Step 3: AddHs — H count matches study-pH protonation state
│     → Step 4: antechamber
│
├── SMILES only, solvated simulation (no protein)
│     → RDKit ETKDG 3D conformer → antechamber → water box only
│
└── SMILES + protein, no co-crystal
      → STOP. Need docking first.
        Ask user to provide docked pose file (mol2/SDF/PDB with H).
        Then use "User file WITH H" branch above.
```

⚠ NEVER run antechamber on crystal PDB directly (no H → wrong atom types)
⚠ NEVER use obabel to add H to crystal ligand (wrong H count)
⚠ NEVER use old align pipeline (PubChem conformer → rigid body align → 3.48 Å RMSD vs crystal)

---

## Branch A — User file WITH H

RDKit preflight — verify H present, no disconnected fragments, no radical electrons, compute formal charge for antechamber `-nc`:
```python
from rdkit import Chem
mol = Chem.MolFromMolFile("ligand.mol2", removeHs=False)
h_count = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() == 1)
assert h_count > 0, "No H — use Branch B"
assert len(Chem.GetMolFrags(mol)) == 1, "Disconnected fragments"
charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())
```
→ proceed to antechamber (Step 6)

---

## Branch B — User file WITHOUT H

```python
from rdkit import Chem
mol = Chem.MolFromMolFile("ligand.mol2", removeHs=True)
charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())
mol_H = Chem.AddHs(mol, addCoords=True)
Chem.SDWriter("ligand_H.sdf").write(mol_H)
```
→ proceed to antechamber with `ligand_H.sdf`

---

## Branch C — Crystal HETATM (main pipeline)

Call the MCP tool — do NOT write or run a user-side `build_ligand.py` script.

```
mcp__amber__build_ligand_from_crystal(
  resname="<3-letter HETATM resname>",
  pdb_path="studies/<study>/raw_pdbs/<pdb_id>.pdb",
  out_sdf="studies/<study>/system/ligand_ready.sdf",
  ph=<study pH>
)
```

Simulation pH is a per-study parameter, not a fixed default. Set it to the same pH used for protein protonation (the propka/`run_propka3` assignment) so ligand and protein ionization states are mutually consistent. Justify the chosen pH in PLAN.md via the tier protocol (lit precedent → Amber 24 manual → training) and pass it explicitly to `build_ligand_from_crystal`. If the tool exposes no pH argument, treat its internal physiological-pH rules as the implementation and document in PLAN.md that the build pH equals the protein protonation pH; flag any mismatch.

Pipeline (executed inside the tool — single MCP call, no network calls):
1. Extract HETATM block, single chain only → RDKit mol with crystal 3D coords preserved exactly
   Bond orders inferred from CONECT records + RDKit valence perception (no CCD/PubChem needed)
2. SMARTS charge rules at the study pH → set formal charges on heavy atoms
   (`SetNoImplicit` + `UpdatePropertyCache` so AddHs computes correct valence)
3. `AddHs(addCoords=True)` → H placed geometrically around crystal coords;
   count matches the study-pH state (protonated amines get NH3+/NH2+/NH+, deprotonated acids get COO-)
4. Write SDF → return net charge for antechamber `-nc`

Return fields:
- `out_sdf`, `charge` / `antechamber_nc_flag` — **study-pH corrected charge** (use directly for `-nc`)
- `charge_source` — `"crystal_formal"` (no ionizable groups) | `"smarts_corrected"` (auto-assigned) | `"flags_present"` (ambiguous group — hard stop)
- `titratable_groups` — list of matched groups + charges applied (e.g. `["amidine(+1)"]`); log in PLAN.md
- `charge_flags` — non-empty → **HARD STOP**: ambiguous pKa group (thiol, phosphonic acid); ask user to provide explicit charge before proceeding
- `h_added` — number of H atoms added
- `heavy_atoms` — number of heavy atoms from crystal

**Charge handling (automatic — no manual verification needed for common groups):**
SMARTS-based correction at the study pH: amidine/guanidine/aliphatic amines → +1; carboxylate/sulfonate/sulfinic acid/tetrazole → -1; phosphate → -2. Crystal formal charges (quaternary N+, pre-ionized groups) preserved. `charge` field correct for `-nc` directly. Confirm these assignments are appropriate at the per-study pH justified in PLAN.md.

**Hard-stop groups** (`charge_flags` non-empty): thiol (pKa 8–10, context-dependent), phosphonic acid (pKa2 ~7, borderline). Ask user: "Ligand contains [group]. Provide formal charge at simulation pH before continuing."

If `status == "error"` with `stage="sanitize"`:
→ exotic valence (metal chelate, unusual oxidation state). Provide pre-protonated SDF → use Branch A.

If `status == "error"` with `stage="crystal_parse"`:
→ malformed HETATM / missing CONECT records. Clean PDB with `pdb4amber` first (SLURM).

⚠ One ligand chain only — tool filters to first chain found; ensure full occupancy before calling
⚠ Works for any ligand including novel/custom compounds not in CCD

### Step 6 — antechamber (SLURM only)

```bash
cd /path/to/studies/<study_name>/system/
antechamber -i ligand_ready.sdf -fi sdf -o ligand.mol2 -fo mol2 \
    -c <CHARGE_METHOD> -at <ATOM_TYPE> -nc <charge>
```

Charge method (`-c`) and atom-type family (`-at`) are per-study choices — do NOT hardwire a default. Justify each in PLAN.md via the tier protocol:
1. **Tier 1 — Lit precedent** from the Step 2b/2c pubmed search (which charge model + atom-type family comparable studies used).
2. **Tier 2 — Amber 24 manual recommendation** via `rag_query` if Tier 1 is empty.
3. **Tier 3 — Training knowledge**, marked `Tier 3`, if both empty. (As background: AM1-BCC `-c bcc` is the cheaper model typically used for screening/binding, while RESP `-c resp` is reserved for publication-grade ΔG or unusual chemistry; GAFF2 `-at gaff2` is the general small-molecule atom-type family. These are starting points to justify against, not defaults to copy.)
4. **Always — Manual validation** via `rag_query("antechamber -c charge method -at atom type GAFF2 AM1-BCC RESP")` to confirm the chosen flag values exist in Amber 24 and that the atom-type family covers the ligand's elements (catches hallucinations).

Document the chosen `-c` and `-at` values with their tier in PLAN.md.

⚠ Never run on login node — `Fatal Error! Cannot properly run sqm`
⚠ Always `cd` into study dir — intermediates (ANTECHAMBER_*.AC, sqm.in/out) write to CWD

Submit with `--gpus 0`, ~1h walltime.

### Step 7 — parmchk2

Run `parmchk2 -i ligand.mol2 -f mol2 -o ligand.frcmod`. Check output for `ATTN: need revision`.

### Step 8 — Verify

```
mcp__amber__read_file_tail(file_path="studies/<study>/logs/antechamber.log", n_chars=3000)
```
Confirm `ligand.mol2` + `ligand.frcmod` both present and non-zero. Search tail for `Total charge` — must match expected formal charge.

⚠ **antechamber atom renaming:** antechamber renames heavy atoms in mol2 (e.g. C11→C1, O11→O1). If loading ligand via PDB HETATM in tLEaP combine, atom names must match mol2. Use `loadMol2` not `loadPdb` for parametrized ligands.

⚠ **Aromatic ligands without CONECT records:** antechamber/sqm may fail with SCF non-convergence if bond orders are wrong. Use `-fi sdf` or `-fi mol2` (with correct bond orders) instead of `-fi pdb` for aromatic/conjugated ligands. PDB format lacks bond order — CONECT records only specify connectivity, not bond type.

---

## Special Cases

### Heme (HEM) — GAFF2 has no Fe atom type
GAFF2 covers only C,N,O,S,P,H,F,Cl,Br,I (Amber manual p311). Antechamber/sqm **cannot** process Fe-containing molecules.

**Fix:** Use Amber 24 built-in Shahrokh et al. (2011) IC6 mol2:
```bash
$AMBERHOME/dat/contrib/Shahrokh_heme/IC6/HEM.mol2
$AMBERHOME/dat/contrib/Shahrokh_heme/IC6/HEM.frcmod
```
Transplant crystal coordinates from raw PDB HETATM block into the mol2 template. For myoglobin (NB proximal His): add `X-fe-nc-X` and `X-fe-nd-X` wildcard torsions to a custom frcmod.

Fe-His proximal bond: add explicit tLEaP bond command `bond sys.93.NE2 sys.154.FE` (this works because Fe uses a custom atom type, not GAFF2).

### Nucleoside Triphosphates (ATP/GTP/CTP) — charge is -4 not -2
All four protons are deprotonated at pH 7:
- α-phosphate: -1, β-phosphate: -1, γ-phosphate monoester: -2 → total **-4**
`build_ligand_from_crystal` only detects the monoester pattern → returns -2. **Always override to nc=-4 for ATP/GTP/CTP.** Verify with antechamber `Total charge` output.

### Biotin (BTN) — charge is -1 not 0
Biotin carboxylate pKa ~2.4 → fully deprotonated at pH 7 → charge **-1**.

---

## Branch D — SMILES, solvated simulation (no protein)

```python
from rdkit import Chem
from rdkit.Chem import AllChem
mol = Chem.AddHs(Chem.MolFromSmiles("<SMILES>"))
AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
AllChem.MMFFOptimizeMolecule(mol)
Chem.SDWriter("ligand_solvated.sdf").write(mol)
```
→ antechamber → tLEaP with water box only (no protein)

---

## tLEaP Integration

```
# Always assign loadMol2 result
MOL = loadMol2 ligand.mol2
loadAmberParams ligand.frcmod
```

Always use absolute paths in tLEaP scripts (relative paths fail with SLURM `-D`).

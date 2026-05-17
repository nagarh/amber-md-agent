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
│     → Step 1: fetch CCD by residue name (primary)
│     → Step 2: fetch PubChem by drug name (cross-validate)
│     → Step 3: compare formulas — match→CCD, mismatch→PubChem SMILES
│     → Step 4: extract crystal HETATM (one chain only)
│     → Step 5: MCS coord-transplant → AddHs
│     → Step 6: antechamber
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

```python
from rdkit import Chem
from rdkit.Chem import rdmolops

mol = Chem.MolFromMolFile("ligand.mol2", removeHs=False)  # or SDF

# Check H present
h_count = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() == 1)
if h_count == 0:
    raise ValueError("No H atoms — use 'User file WITHOUT H' branch")

# Check no disconnected fragments
frags = rdmolops.GetMolFrags(mol)
if len(frags) > 1:
    raise ValueError(f"Molecule has {len(frags)} disconnected fragments")

# Check no radical electrons (broken valence)
radicals = [a.GetIdx() for a in mol.GetAtoms() if a.GetNumRadicalElectrons() > 0]
if radicals:
    raise ValueError(f"Radical electrons on atoms {radicals} — check structure")

# Formal charge for antechamber -nc
charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())
print(f"Formal charge: {charge}")
```

→ proceed to antechamber (Step 6)

---

## Branch B — User file WITHOUT H

```python
from rdkit import Chem

mol = Chem.MolFromMolFile("ligand.mol2", removeHs=True)  # or SDF
charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())

# AddHs — H count from valence + bond orders (reliable for mol2/SDF)
mol_H = Chem.AddHs(mol, addCoords=True)
h_added = sum(1 for a in mol_H.GetAtoms() if a.GetAtomicNum() == 1)
print(f"H added: {h_added}  charge: {charge}")

writer = Chem.SDWriter("ligand_H.sdf")
writer.write(mol_H)
writer.close()
```

→ proceed to antechamber with `ligand_H.sdf`

---

## Branch C — Crystal HETATM (main pipeline)

Write `studies/<study>/system/build_ligand.py` using the `Write` tool, then run it with `Bash` using the `amber_development` env:
```bash
/home/hn533621/.conda/envs/amber_development/bin/python studies/<study>/system/build_ligand.py
```

### Steps 1–5 script (build_ligand.py)

Fill in `RESNAME`, `PDB_PATH`, `DRUG_NAME`, `OUT_SDF` before writing.

```python
#!/usr/bin/env python3
import sys, urllib.request
sys.path.insert(0, 'mcp_servers/')
from rdkit import Chem
from rdkit.Chem import AllChem, rdFMCS, rdMolDescriptors

RESNAME   = "<3-letter residue name>"   # e.g. "032"
PDB_PATH  = "<path/to/raw.pdb>"
DRUG_NAME = "<drug name>"               # e.g. "vemurafenib"
OUT_SDF   = "<path/to/ligand_ready.sdf>"

# ── Step 1: CCD fetch ─────────────────────────────────────────
url  = f"https://files.rcsb.org/ligands/download/{RESNAME}_ideal.sdf"
data = urllib.request.urlopen(url, timeout=15).read().decode()
ccd_mol   = Chem.MolFromMolBlock(data, removeHs=False, sanitize=True)
ccd_heavy = Chem.RemoveHs(ccd_mol)
ccd_formula = rdMolDescriptors.CalcMolFormula(ccd_heavy)
ccd_charge  = sum(a.GetFormalCharge() for a in ccd_mol.GetAtoms())
ccd_H       = ccd_mol.GetNumAtoms() - ccd_heavy.GetNumAtoms()
print(f"CCD: {ccd_formula}  charge={ccd_charge}  H={ccd_H}")

# ── Step 2: PubChem cross-validate ────────────────────────────
from pubchem_server import search_compound
result     = search_compound(DRUG_NAME)
hit        = result["results"][0]
pub_smiles = hit.get("isomeric_smiles") or hit.get("canonical_smiles")
pub_formula = hit.get("formula", "")
pub_charge  = hit.get("formal_charge", 0)
print(f"PubChem: {pub_formula}  charge={pub_charge}")

# ── Step 3: Cross-validate ────────────────────────────────────
if ccd_formula == pub_formula:
    template = ccd_heavy
    charge   = ccd_charge
    print("CCD matches PubChem — using CCD bond orders")
else:
    print(f"WARNING: CCD ({ccd_formula}) != PubChem ({pub_formula})")
    print("Using PubChem SMILES for bond orders")
    template = Chem.MolFromSmiles(pub_smiles)
    charge   = pub_charge
    ccd_H    = sum(1 for a in Chem.AddHs(template).GetAtoms() if a.GetAtomicNum()==1)

# ── Step 4: Extract crystal HETATM (one chain only) ───────────
seen_chain, lines = None, []
with open(PDB_PATH) as f:
    for l in f:
        if l.startswith("HETATM") and RESNAME in l[17:20]:
            chain = l[21]
            if seen_chain is None:
                seen_chain = chain
            if chain == seen_chain:
                lines.append(l)
if not lines:
    raise ValueError(f"No HETATM for {RESNAME} in {PDB_PATH}")
crystal_mol = Chem.MolFromPDBBlock("".join(lines)+"END\n", removeHs=True, sanitize=False)
Chem.FastFindRings(crystal_mol)
print(f"Crystal heavy atoms: {crystal_mol.GetNumAtoms()}")

# ── Step 5: MCS coord-transplant + AddHs ──────────────────────
mcs = rdFMCS.FindMCS(
    [template, crystal_mol],
    bondCompare=rdFMCS.BondCompare.CompareAny,
    atomCompare=rdFMCS.AtomCompare.CompareElements,
    matchValences=False, timeout=60
)
match_pct = mcs.numAtoms / template.GetNumAtoms()
print(f"MCS: {mcs.numAtoms}/{template.GetNumAtoms()} ({match_pct:.0%})")
if match_pct < 0.9:
    # Options for non-standard ligands with <90% MCS match:
    # 1. Modified residue (PTM, metal chelate) → provide SMILES manually via Branch D
    # 2. Covalent ligand → extract warhead+linker separately, parametrize as two residues
    # 3. Wrong CCD code → check PubChem formula match, try alternative CCD residue name
    # 4. Prodrug/metabolite in crystal → confirm correct compound identity with user
    raise ValueError(f"MCS match {match_pct:.0%} < 90% — identity mismatch. See options above. Provide SMILES manually or use Branch D.")

mcs_mol    = Chem.MolFromSmarts(mcs.smartsString)
tmpl_match = template.GetSubstructMatch(mcs_mol)
crys_match = crystal_mol.GetSubstructMatch(mcs_mol)

new_mol = Chem.RWMol(template)
new_mol.RemoveAllConformers()
conf     = Chem.Conformer(new_mol.GetNumAtoms())
cry_conf = crystal_mol.GetConformer()
matched  = set(tmpl_match)

for i in range(new_mol.GetNumAtoms()):
    conf.SetAtomPosition(i, (0.0, 0.0, 0.0))
for ti, ci in zip(tmpl_match, crys_match):
    p = cry_conf.GetAtomPosition(ci)
    conf.SetAtomPosition(ti, (p.x, p.y, p.z))

# Unmatched atoms: CCD ideal coords if available, else neighbor centroid
unmatched = [i for i in range(template.GetNumAtoms()) if i not in matched]
if unmatched:
    print(f"WARNING: {len(unmatched)} unmatched atoms — placed from ideal/neighbor geometry")
    try:
        ideal_conf = ccd_heavy.GetConformer()
        for idx in unmatched:
            p = ideal_conf.GetAtomPosition(idx)
            conf.SetAtomPosition(idx, (p.x, p.y, p.z))
    except Exception:
        for idx in unmatched:
            nbrs = [n.GetIdx() for n in new_mol.GetAtomWithIdx(idx).GetNeighbors() if n.GetIdx() in matched]
            if nbrs:
                ps = [conf.GetAtomPosition(n) for n in nbrs]
                conf.SetAtomPosition(idx, (sum(p.x for p in ps)/len(ps),
                                           sum(p.y for p in ps)/len(ps),
                                           sum(p.z for p in ps)/len(ps)))

new_mol.AddConformer(conf, assignId=True)
mol_H   = Chem.AddHs(new_mol, addCoords=True)
h_added = sum(1 for a in mol_H.GetAtoms() if a.GetAtomicNum()==1)
print(f"H added: {h_added}  (expected {ccd_H})  charge: {charge}")

Chem.SDWriter(OUT_SDF).write(mol_H)
print(f"Written: {OUT_SDF}")
print(f"antechamber -nc flag: {charge}")
```

⚠ Filter by one chain — multiple chains = concatenated atoms = MCS failure

### Step 6 — antechamber (SLURM only)

Read `charge` from script output above, then submit:

```bash
# In SLURM script — cd into study directory FIRST
cd /path/to/studies/<study_name>/system/
antechamber -i ligand_ready.sdf -fi sdf -o ligand.mol2 -fo mol2 -c bcc -at gaff2 -nc <charge>
```

⚠ Never run on login node — `Fatal Error! Cannot properly run sqm`
⚠ Always `cd` into study dir — intermediates (ANTECHAMBER_*.AC, sqm.in/out, ATOMTYPE.INF) write to CWD

Submit with `--gpus 0`, ~1h walltime.

### Step 7 — parmchk2

```bash
parmchk2 -i ligand.mol2 -f mol2 -o ligand.frcmod
```

Check output for `ATTN: need revision` — missing parameters need manual attention.

### Step 8 — Verify

```bash
ls -lh ligand.mol2 ligand.frcmod   # both must exist, non-zero size
grep "Total charge" antechamber.log  # must match expected formal charge
```

---

## Branch D — SMILES, solvated simulation (no protein)

```python
from rdkit import Chem
from rdkit.Chem import AllChem

smiles = "CC(=O)Oc1ccccc1C(=O)O"   # user-provided
mol = Chem.MolFromSmiles(smiles)
charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())

mol_H = Chem.AddHs(mol)
AllChem.EmbedMolecule(mol_H, AllChem.ETKDGv3())
AllChem.MMFFOptimizeMolecule(mol_H)

writer = Chem.SDWriter("ligand_solvated.sdf")
writer.write(mol_H)
writer.close()
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

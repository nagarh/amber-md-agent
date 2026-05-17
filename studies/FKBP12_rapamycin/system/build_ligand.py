#!/usr/bin/env python3
"""Branch C: Crystal HETATM pipeline for RAP (rapamycin) from 2DG3."""
import sys, urllib.request
sys.path.insert(0, 'mcp_servers/')
from rdkit import Chem
from rdkit.Chem import AllChem, rdFMCS, rdMolDescriptors

RESNAME   = "RAP"
PDB_PATH  = "studies/FKBP12_rapamycin/raw_pdbs/2DG3.pdb"
DRUG_NAME = "rapamycin"
OUT_SDF   = "studies/FKBP12_rapamycin/system/ligand_ready.sdf"

# ── Step 1: CCD fetch (with PubChem SDF fallback) ─────────────
ccd_endpoints = [
    f"https://files.rcsb.org/ligands/download/{RESNAME}_ideal.sdf",
    f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/CID/5284616/SDF",
]
ccd_mol = None
for url in ccd_endpoints:
    try:
        req  = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        data = urllib.request.urlopen(req, timeout=15).read().decode()
        ccd_mol = Chem.MolFromMolBlock(data, removeHs=False, sanitize=True)
        if ccd_mol is not None:
            print(f"CCD source: {url}")
            break
    except Exception as e:
        print(f"CCD fetch failed {url}: {e}")
if ccd_mol is None:
    raise RuntimeError("All CCD endpoints failed — check network")

ccd_heavy   = Chem.RemoveHs(ccd_mol)
ccd_formula = rdMolDescriptors.CalcMolFormula(ccd_heavy)
ccd_charge  = sum(a.GetFormalCharge() for a in ccd_mol.GetAtoms())
ccd_H       = ccd_mol.GetNumAtoms() - ccd_heavy.GetNumAtoms()
print(f"CCD: {ccd_formula}  charge={ccd_charge}  H={ccd_H}")

# ── Step 2: PubChem cross-validate ────────────────────────────
from pubchem_server import search_compound
result      = search_compound(DRUG_NAME)
hit         = result["results"][0]
pub_formula = hit.get("formula", "")
pub_charge  = hit.get("formal_charge", 0)
pub_smiles  = hit.get("isomeric_smiles") or hit.get("canonical_smiles")
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

# ── Step 4: Extract crystal HETATM (chain A only) ─────────────
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
    raise ValueError(f"MCS match {match_pct:.0%} < 90% — identity mismatch.")

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

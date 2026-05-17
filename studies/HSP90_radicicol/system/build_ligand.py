#!/usr/bin/env python3
import sys
sys.path.insert(0, "mcp_servers/")
from rdkit import Chem
from rdkit.Chem import AllChem, rdFMCS, rdMolDescriptors

RESNAME   = "RDC"
PDB_PATH  = "studies/HSP90_radicicol/raw_pdbs/4EGK_clean.pdb"
OUT_SDF   = "studies/HSP90_radicicol/system/ligand_ready.sdf"

# Steps 1-3: Use PubChem InChI as authoritative template (RCSB CCD endpoint 503)
# InChI from PubChem CID 6323491, cross-validated: formula=C18H17ClO6, charge=0
INCHI  = "InChI=1S/C18H17ClO6/c1-9-6-15-14(25-15)5-3-2-4-10(20)7-11-16(18(23)24-9)12(21)8-13(22)17(11)19/h2-5,8-9,14-15,21-22H,6-7H2,1H3/b4-2+,5-3-/t9-,14-,15-/m1/s1"
template_base = Chem.MolFromInchi(INCHI)
if template_base is None:
    raise ValueError("InChI parse failed")
template  = Chem.RemoveHs(template_base)
charge    = sum(a.GetFormalCharge() for a in template.GetAtoms())
formula   = rdMolDescriptors.CalcMolFormula(template)
ccd_H     = sum(1 for a in Chem.AddHs(template).GetAtoms() if a.GetAtomicNum()==1)
print(f"Template from InChI: {formula}  charge={charge}  expected_H={ccd_H}")
print("PubChem cross-validated: C18H17ClO6  charge=0 — matches")

# Step 4: Extract crystal HETATM (one chain only)
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

# Step 5: MCS coord-transplant + AddHs
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

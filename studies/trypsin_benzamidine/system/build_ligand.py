#!/usr/bin/env python3
"""Build BEN benzamidinium (+1) ligand SDF.
CCD ideal is neutral form; physiological pH 7 form is amidinium +1 (pKa~11.6).
Use cationic SMILES + transplant crystal coords via MCS."""
import sys
sys.path.insert(0, "mcp_servers/")
from rdkit import Chem
from rdkit.Chem import AllChem, rdFMCS, rdMolDescriptors

PDB_PATH = "studies/trypsin_benzamidine/raw_pdbs/3PTB.pdb"
RESNAME  = "BEN"
OUT_SDF  = "studies/trypsin_benzamidine/system/ligand_ready.sdf"
SMILES   = "NC(=[NH2+])c1ccccc1"  # benzamidinium cation

template = Chem.MolFromSmiles(SMILES)
charge = sum(a.GetFormalCharge() for a in template.GetAtoms())
formula = rdMolDescriptors.CalcMolFormula(template)
print(f"Template: SMILES={SMILES}  formula={formula}  charge={charge}  heavy={template.GetNumAtoms()}")
assert charge == 1, f"Expected +1, got {charge}"

# 3D embed for unmatched atom fallback
template_3d = Chem.AddHs(template, addCoords=False)
AllChem.EmbedMolecule(template_3d, AllChem.ETKDGv3())
AllChem.MMFFOptimizeMolecule(template_3d)
template_3d_heavy = Chem.RemoveHs(template_3d)

# Extract crystal HETATM (chain A only)
seen_chain, lines = None, []
with open(PDB_PATH) as f:
    for l in f:
        if l.startswith("HETATM") and RESNAME in l[17:20]:
            chain = l[21]
            if seen_chain is None:
                seen_chain = chain
            if chain == seen_chain:
                lines.append(l)
crystal_mol = Chem.MolFromPDBBlock("".join(lines)+"END\n", removeHs=True, sanitize=False)
Chem.FastFindRings(crystal_mol)
print(f"Crystal heavy atoms: {crystal_mol.GetNumAtoms()}")

# MCS template vs crystal
mcs = rdFMCS.FindMCS(
    [template_3d_heavy, crystal_mol],
    bondCompare=rdFMCS.BondCompare.CompareAny,
    atomCompare=rdFMCS.AtomCompare.CompareElements,
    matchValences=False, timeout=60,
)
match_pct = mcs.numAtoms / template_3d_heavy.GetNumAtoms()
print(f"MCS: {mcs.numAtoms}/{template_3d_heavy.GetNumAtoms()} ({match_pct:.0%})")

mcs_mol = Chem.MolFromSmarts(mcs.smartsString)
tmpl_match = template_3d_heavy.GetSubstructMatch(mcs_mol)
crys_match = crystal_mol.GetSubstructMatch(mcs_mol)

new_mol = Chem.RWMol(template_3d_heavy)
new_mol.RemoveAllConformers()
conf = Chem.Conformer(new_mol.GetNumAtoms())
cry_conf = crystal_mol.GetConformer()
matched = set(tmpl_match)
for i in range(new_mol.GetNumAtoms()):
    conf.SetAtomPosition(i, (0.0, 0.0, 0.0))
for ti, ci in zip(tmpl_match, crys_match):
    p = cry_conf.GetAtomPosition(ci)
    conf.SetAtomPosition(ti, (p.x, p.y, p.z))

# Unmatched: use embedded coords from template_3d_heavy
unmatched = [i for i in range(template_3d_heavy.GetNumAtoms()) if i not in matched]
if unmatched:
    print(f"WARN: {len(unmatched)} unmatched template atoms — using ETKDG ideal coords")
    ideal_conf = template_3d_heavy.GetConformer()
    for idx in unmatched:
        p = ideal_conf.GetAtomPosition(idx)
        conf.SetAtomPosition(idx, (p.x, p.y, p.z))

new_mol.AddConformer(conf, assignId=True)
mol_H = Chem.AddHs(new_mol, addCoords=True)
h_added = sum(1 for a in mol_H.GetAtoms() if a.GetAtomicNum() == 1)
print(f"H added: {h_added}  charge: {charge}")

Chem.SDWriter(OUT_SDF).write(mol_H)
print(f"Written: {OUT_SDF}")
print(f"NET_CHARGE_FOR_ANTECHAMBER: {charge}")

#!/usr/bin/env python3
import sys, urllib.request
sys.path.insert(0, "mcp_servers/")
from rdkit import Chem
from rdkit.Chem import AllChem, rdFMCS, rdMolDescriptors

RESNAME  = "STI"
PDB_PATH = "studies/EGFR_erlotinib/raw_pdbs/1IEP.pdb"
OUT_SDF  = "studies/EGFR_erlotinib/system/ligand_ready.sdf"

# Step 1: CCD fetch
url  = f"https://files.rcsb.org/ligands/download/{RESNAME}_ideal.sdf"
data = urllib.request.urlopen(url, timeout=15).read().decode()
ccd_mol   = Chem.MolFromMolBlock(data, removeHs=False, sanitize=True)
ccd_heavy = Chem.RemoveHs(ccd_mol)
ccd_formula = rdMolDescriptors.CalcMolFormula(ccd_heavy)
ccd_charge  = sum(a.GetFormalCharge() for a in ccd_mol.GetAtoms())
ccd_H       = ccd_mol.GetNumAtoms() - ccd_heavy.GetNumAtoms()
print(f"CCD: {ccd_formula}  charge={ccd_charge}  H={ccd_H}")

# Step 2: Extract crystal HETATM (chain A only)
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
    raise ValueError(f"No HETATM for {RESNAME}")
print(f"Crystal heavy atoms: {len(lines)}  (chain {seen_chain})")
crystal_mol = Chem.MolFromPDBBlock("".join(lines)+"END\n", removeHs=True, sanitize=False)
Chem.FastFindRings(crystal_mol)

# Step 3: MCS coord-transplant
mcs = rdFMCS.FindMCS(
    [ccd_heavy, crystal_mol],
    bondCompare=rdFMCS.BondCompare.CompareAny,
    atomCompare=rdFMCS.AtomCompare.CompareElements,
    matchValences=False, timeout=60)
match_pct = mcs.numAtoms / ccd_heavy.GetNumAtoms()
print(f"MCS: {mcs.numAtoms}/{ccd_heavy.GetNumAtoms()} ({match_pct:.0%})")
if match_pct < 0.9:
    raise ValueError(f"MCS {match_pct:.0%} < 90% — identity mismatch")

mcs_mol    = Chem.MolFromSmarts(mcs.smartsString)
ccd_match  = ccd_heavy.GetSubstructMatch(mcs_mol)
crys_match = crystal_mol.GetSubstructMatch(mcs_mol)

new_mol = Chem.RWMol(ccd_heavy)
new_mol.RemoveAllConformers()
conf     = Chem.Conformer(new_mol.GetNumAtoms())
cry_conf = crystal_mol.GetConformer()
matched  = set(ccd_match)

for i in range(new_mol.GetNumAtoms()):
    conf.SetAtomPosition(i, (0.0, 0.0, 0.0))
for ci, cj in zip(ccd_match, crys_match):
    p = cry_conf.GetAtomPosition(cj)
    conf.SetAtomPosition(ci, (p.x, p.y, p.z))

unmatched = [i for i in range(ccd_heavy.GetNumAtoms()) if i not in matched]
if unmatched:
    print(f"WARNING: {len(unmatched)} unmatched — neighbour centroid fallback")
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
print(f"H added: {h_added}  (CCD expected: {ccd_H})  charge: {ccd_charge}")

Chem.SDWriter(OUT_SDF).write(mol_H)
print(f"Written: {OUT_SDF}")
print(f"antechamber -nc flag: {ccd_charge}")

#!/usr/bin/env python3
"""
Branch C ligand prep for IBP (ibuprofen) from 2BXG chain A.
Produces two SDF files: one per binding site (A2001, A2002).
Same CCD/PubChem template used for both — coordinates from crystal.
"""
import sys, urllib.request
sys.path.insert(0, 'mcp_servers/')
from rdkit import Chem
from rdkit.Chem import AllChem, rdFMCS, rdMolDescriptors

RESNAME   = "IBP"
PDB_PATH  = "studies/HSA_ibuprofen/raw_pdbs/2BXG.pdb"
DRUG_NAME = "ibuprofen"
OUT_DIR   = "studies/HSA_ibuprofen/system"

# ── Step 1: CCD fetch ─────────────────────────────────────────────────────────
url  = f"https://files.rcsb.org/ligands/download/{RESNAME}_ideal.sdf"
data = urllib.request.urlopen(url, timeout=15).read().decode()
ccd_mol   = Chem.MolFromMolBlock(data, removeHs=False, sanitize=True)
ccd_heavy = Chem.RemoveHs(ccd_mol)
ccd_formula = rdMolDescriptors.CalcMolFormula(ccd_heavy)
ccd_charge  = sum(a.GetFormalCharge() for a in ccd_mol.GetAtoms())
ccd_H       = ccd_mol.GetNumAtoms() - ccd_heavy.GetNumAtoms()
print(f"CCD: {ccd_formula}  charge={ccd_charge}  H={ccd_H}")

# ── Step 2: PubChem cross-validate ───────────────────────────────────────────
from pubchem_server import search_compound
result     = search_compound(DRUG_NAME)
hit        = result["results"][0]
pub_smiles = hit.get("isomeric_smiles") or hit.get("canonical_smiles")
pub_formula = hit.get("formula", "")
pub_charge  = hit.get("formal_charge", 0)
print(f"PubChem: {pub_formula}  charge={pub_charge}")

# ── Step 3: Cross-validate ────────────────────────────────────────────────────
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

def extract_and_build(pdb_path, resname, chain, resnum, out_sdf, template, ccd_heavy, ccd_H, charge):
    """Extract one ligand pose from HETATM records and build SDF with H."""
    lines = []
    with open(pdb_path) as f:
        for l in f:
            if l.startswith("HETATM") and l[17:20].strip() == resname:
                c = l[21]          # chain col 22 (1-indexed)
                r = l[22:26].strip()  # resnum cols 23-26
                if c == chain and r == resnum:
                    lines.append(l)
    if not lines:
        raise ValueError(f"No HETATM for {resname} chain {chain} res {resnum} in {pdb_path}")
    crystal_mol = Chem.MolFromPDBBlock("".join(lines)+"END\n", removeHs=True, sanitize=False)
    Chem.FastFindRings(crystal_mol)
    print(f"  Crystal heavy atoms ({resnum}): {crystal_mol.GetNumAtoms()}")

    # ── Step 5: MCS coord-transplant + AddHs ─────────────────────────────────
    mcs = rdFMCS.FindMCS(
        [template, crystal_mol],
        bondCompare=rdFMCS.BondCompare.CompareAny,
        atomCompare=rdFMCS.AtomCompare.CompareElements,
        matchValences=False, timeout=60
    )
    match_pct = mcs.numAtoms / template.GetNumAtoms()
    print(f"  MCS: {mcs.numAtoms}/{template.GetNumAtoms()} ({match_pct:.0%})")
    if match_pct < 0.9:
        raise ValueError(f"MCS match {match_pct:.0%} < 90% — identity mismatch")

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
        print(f"  WARNING: {len(unmatched)} unmatched atoms — placed from ideal/neighbor geometry")
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
    print(f"  H added: {h_added}  (expected {ccd_H})  charge: {charge}")
    Chem.SDWriter(out_sdf).write(mol_H)
    print(f"  Written: {out_sdf}")
    return charge

print("\n--- Building IBP A2001 (Sudlow site II) ---")
charge = extract_and_build(
    PDB_PATH, RESNAME, 'A', '2001',
    f"{OUT_DIR}/ibp_A2001_ready.sdf",
    template, ccd_heavy, ccd_H, charge
)

print("\n--- Building IBP A2002 (secondary site) ---")
extract_and_build(
    PDB_PATH, RESNAME, 'A', '2002',
    f"{OUT_DIR}/ibp_A2002_ready.sdf",
    template, ccd_heavy, ccd_H, charge
)

print(f"\nantechamber -nc flag for both: {charge}")
print("Done. Run antechamber on each SDF file (SLURM).")

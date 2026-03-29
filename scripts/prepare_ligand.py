#!/usr/bin/env python3
"""
Ligand preparation for Amber MD — the CORRECT workflow.

This script replaces trial-and-error ligand parametrization with a
deterministic pipeline:

  1. Input: crystal PDB ligand (heavy atoms only, no H, no connectivity)
  2. Fetch: PubChem 3D conformer SDF (correct H count, proper connectivity)
  3. Align: RDKit MCS alignment of PubChem conformer onto crystal pose
  4. Output: Aligned SDF ready for antechamber

After this script, run antechamber on the aligned SDF (via SLURM):
    antechamber -i aligned.sdf -fi sdf -o ligand.mol2 -fo mol2 \
                -c bcc -at gaff2 -s 2 -nc <charge>

Why this exists:
  - Crystal PDBs have NO hydrogens and NO connectivity → antechamber fails
  - obabel adds wrong H count from guessed distances
  - PubChem SDF has correct connectivity + H but different 3D coordinates
  - RDKit MCS alignment puts PubChem geometry into the crystal binding pose
  - This is the ONLY reliable path. It was learned the hard way (CDK4 study).

Usage:
    python scripts/prepare_ligand.py \\
        --crystal-pdb ligand_from_crystal.pdb \\
        --pubchem-sdf pubchem_conformer.sdf \\
        --output aligned_ligand.sdf \\
        [--ligand-code 6ZV]

Or from Python:
    from scripts.prepare_ligand import align_ligand_to_crystal
    rmsd = align_ligand_to_crystal("crystal.pdb", "pubchem.sdf", "aligned.sdf")
"""

import argparse
import sys
from pathlib import Path

def align_ligand_to_crystal(crystal_pdb, pubchem_sdf, output_sdf, ligand_code=None):
    """Align PubChem 3D conformer onto crystal ligand pose using MCS.

    Args:
        crystal_pdb: Path to crystal PDB with ligand heavy atoms
        pubchem_sdf: Path to PubChem 3D conformer SDF (with H)
        output_sdf: Output path for aligned SDF
        ligand_code: Optional 3-letter code to extract from multi-residue PDB

    Returns:
        dict with rmsd, n_matched_atoms, output_file
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem, rdFMCS, rdMolAlign, rdMolTransforms
    except ImportError:
        return {"error": "RDKit not installed. Install with: pip install rdkit"}

    # Load crystal structure (heavy atoms only)
    mol_crystal = Chem.MolFromPDBFile(str(crystal_pdb), removeHs=True, sanitize=False)
    if mol_crystal is None:
        # Try extracting specific ligand from PDB
        if ligand_code:
            lines = []
            with open(crystal_pdb) as f:
                for line in f:
                    if line.startswith(("HETATM", "ATOM")):
                        resname = line[17:20].strip()
                        if resname == ligand_code:
                            lines.append(line)
            if lines:
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.pdb', delete=False) as tmp:
                    tmp.writelines(lines)
                    tmp.write("END\n")
                    tmp_path = tmp.name
                mol_crystal = Chem.MolFromPDBFile(tmp_path, removeHs=True, sanitize=False)
                Path(tmp_path).unlink()

        if mol_crystal is None:
            return {"error": f"Could not parse crystal PDB: {crystal_pdb}"}

    # Load PubChem conformer (with H)
    mol_pubchem = Chem.SDMolSupplier(str(pubchem_sdf), removeHs=False)[0]
    if mol_pubchem is None:
        return {"error": f"Could not parse PubChem SDF: {pubchem_sdf}"}

    # Heavy-atom version of PubChem mol for MCS matching
    mol_pubchem_heavy = Chem.RemoveHs(mol_pubchem)

    # Find Maximum Common Substructure
    try:
        Chem.SanitizeMol(mol_crystal)
    except Exception:
        pass  # Crystal mol may have valence issues without H
    try:
        Chem.SanitizeMol(mol_pubchem_heavy)
    except Exception:
        pass

    mcs = rdFMCS.FindMCS(
        [mol_pubchem_heavy, mol_crystal],
        timeout=60,
        bondCompare=rdFMCS.BondCompare.CompareAny,
        atomCompare=rdFMCS.AtomCompare.CompareElements,
    )

    if mcs.numAtoms == 0:
        return {"error": "MCS found 0 matching atoms — structures may be incompatible"}

    patt = Chem.MolFromSmarts(mcs.smartsString)
    match_pubchem = mol_pubchem_heavy.GetSubstructMatch(patt)
    match_crystal = mol_crystal.GetSubstructMatch(patt)

    if not match_pubchem or not match_crystal:
        return {"error": "Could not match MCS pattern to molecules"}

    atom_map = list(zip(match_pubchem, match_crystal))

    # Compute alignment transform and apply to full molecule (with H)
    rmsd, transform = rdMolAlign.GetAlignmentTransform(
        mol_pubchem_heavy, mol_crystal, atomMap=atom_map
    )
    rdMolTransforms.TransformConformer(mol_pubchem.GetConformer(), transform)

    # Write aligned SDF
    writer = Chem.SDWriter(str(output_sdf))
    writer.write(mol_pubchem)
    writer.close()

    return {
        "output_file": str(output_sdf),
        "rmsd": round(rmsd, 4),
        "n_matched_atoms": mcs.numAtoms,
        "n_crystal_heavy": mol_crystal.GetNumAtoms(),
        "n_pubchem_total": mol_pubchem.GetNumAtoms(),
        "n_pubchem_heavy": mol_pubchem_heavy.GetNumAtoms(),
        "mcs_smarts": mcs.smartsString[:100],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Align PubChem ligand conformer to crystal pose for antechamber input"
    )
    parser.add_argument("--crystal-pdb", required=True, help="Crystal PDB with ligand heavy atoms")
    parser.add_argument("--pubchem-sdf", required=True, help="PubChem 3D conformer SDF (with H)")
    parser.add_argument("--output", required=True, help="Output aligned SDF")
    parser.add_argument("--ligand-code", default=None, help="3-letter residue code to extract from PDB")

    args = parser.parse_args()
    result = align_ligand_to_crystal(args.crystal_pdb, args.pubchem_sdf, args.output, args.ligand_code)

    import json
    print(json.dumps(result, indent=2))

    if "error" in result:
        sys.exit(1)
    else:
        print(f"\nAligned ligand written to {result['output_file']}")
        print(f"RMSD (heavy atoms): {result['rmsd']:.4f} Å")
        print(f"Matched {result['n_matched_atoms']} / {result['n_crystal_heavy']} heavy atoms")
        print(f"\nNext step: submit antechamber on this SDF via SLURM")


if __name__ == "__main__":
    main()

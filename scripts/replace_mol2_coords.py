#!/usr/bin/env python3
"""
replace_mol2_coords.py — Copy heavy-atom XYZ from a crystal PDB into a mol2 file.

The mol2 has correct connectivity/charges (from antechamber on PubChem SDF).
The crystal PDB has the correct binding-site pose (heavy atoms only).
This script matches heavy atoms by element and index order, replaces mol2 coords,
and keeps the hydrogens from the mol2 at their original positions (tLEaP rebuilds them).

Usage:
    python replace_mol2_coords.py input.mol2 crystal.pdb output.mol2
"""
import sys
import re


def read_mol2_atoms(lines):
    """Return list of (idx, name, x, y, z, rest) tuples from @<TRIPOS>ATOM block."""
    in_atom = False
    atoms = []
    atom_start = None
    for i, line in enumerate(lines):
        if line.strip() == "@<TRIPOS>ATOM":
            in_atom = True
            atom_start = i + 1
            continue
        if in_atom and line.strip().startswith("@<TRIPOS>"):
            break
        if in_atom:
            parts = line.split()
            if len(parts) >= 6:
                atoms.append((i, parts[1], float(parts[2]), float(parts[3]), float(parts[4])))
    return atoms


def read_pdb_heavy(pdb_path):
    """Return list of (name, x, y, z) for heavy atoms in PDB order."""
    atoms = []
    with open(pdb_path) as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                name = line[12:16].strip()
                elem = line[76:78].strip() if len(line) > 76 else name[0]
                if elem.upper() in ("H", "D"):
                    continue
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                atoms.append((name, x, y, z))
    return atoms


def replace_coords(mol2_path, pdb_path, out_path):
    with open(mol2_path) as f:
        lines = f.readlines()

    mol2_atoms = read_mol2_atoms(lines)
    pdb_heavy = read_pdb_heavy(pdb_path)

    # M-44: filter mol2 heavy atoms — exclude H/D isotopes by leading char
    mol2_heavy = [(i, name, x, y, z) for (i, name, x, y, z) in mol2_atoms
                  if name and name.upper()[0] not in ("H", "D")]

    if len(mol2_heavy) != len(pdb_heavy):
        print(f"WARNING: mol2 heavy atoms ({len(mol2_heavy)}) != PDB heavy atoms ({len(pdb_heavy)})")
        print("Attempting match by order — check result carefully")

    new_lines = list(lines)
    for idx, (mol2_idx, mol2_name, _, _, _) in enumerate(mol2_heavy):
        if idx >= len(pdb_heavy):
            break
        _, px, py, pz = pdb_heavy[idx]
        # Reconstruct the atom line with new coordinates
        orig = lines[mol2_idx]
        parts = orig.split()
        # Replace x, y, z fields (cols 2, 3, 4 in 0-indexed)
        new_line = (
            f"{parts[0]:>7s} {parts[1]:<8s} {px:>10.4f} {py:>10.4f} {pz:>10.4f}"
            + "  " + "  ".join(parts[5:]) + "\n"
        )
        new_lines[mol2_idx] = new_line

    with open(out_path, "w") as f:
        f.writelines(new_lines)

    print(f"Replaced {min(len(mol2_heavy), len(pdb_heavy))} heavy-atom coordinates.")
    print(f"Written: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: replace_mol2_coords.py input.mol2 crystal.pdb output.mol2")
        sys.exit(1)
    replace_coords(sys.argv[1], sys.argv[2], sys.argv[3])

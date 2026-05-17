#!/usr/bin/env python3
"""
cap_protein.py — Add ACE/NME capping groups using AmberMDFlow add_caps.py.
Pre-processes PDB to remove incomplete terminal residues before capping.

Usage:
    python cap_protein.py input.pdb output_capped.pdb
"""
import sys
import subprocess
import os
import tempfile

ADD_CAPS = os.path.join(os.path.dirname(__file__), "add_caps.py")


def strip_incomplete_termini(input_pdb, output_pdb):
    """
    Prepare each chain for add_caps.py:
      1. Strip any existing ACE/NME caps (add_caps.py always adds them fresh).
      2. Remove terminal residues that lack a complete backbone (C, CA, O/OXT).
    add_caps.py's get_nme_pos requires O or OXT on the last residue.
    add_caps.py's get_ace_pos requires CA on the first residue.
    """
    import MDAnalysis as mda
    import warnings
    warnings.filterwarnings("ignore")

    u = mda.Universe(input_pdb)
    keep_indices = []

    for seg in u.segments:
        chain = u.select_atoms(f"segid {seg.segid}")
        residues = chain.residues

        # 1. Drop leading ACE and trailing NME (already capped — add_caps adds them fresh)
        res_list = list(residues)
        while res_list and res_list[0].resname.strip().upper() == "ACE":
            print(f"  [{seg.segid}] Stripped existing ACE cap at resid {res_list[0].resid}")
            res_list.pop(0)
        while res_list and res_list[-1].resname.strip().upper() == "NME":
            print(f"  [{seg.segid}] Stripped existing NME cap at resid {res_list[-1].resid}")
            res_list.pop()

        if not res_list:
            print(f"  [{seg.segid}] Warning: no residues left after stripping caps — skipping segment")
            continue

        resids_clean = [r.resid for r in res_list]

        # 2. Find last residue with complete backbone for NME placement
        last_good = None
        for rid in reversed(resids_clean):
            res_atoms = set(u.select_atoms(f"segid {seg.segid} and resid {rid}").names)
            if ('C' in res_atoms and 'CA' in res_atoms and
                    ('O' in res_atoms or 'OXT' in res_atoms)):
                last_good = rid
                break

        if last_good is None:
            print(f"  [{seg.segid}] Warning: no residue with complete backbone found — skipping segment")
            continue

        # Keep atoms in this segment that are in resids_clean and <= last_good
        valid_resids = set(rid for rid in resids_clean if rid <= last_good)
        min_rid = min(valid_resids)
        max_rid = max(valid_resids)
        sel = u.select_atoms(
            f"segid {seg.segid} and resid {min_rid}-{max_rid}"
        )
        keep_indices.extend(sel.indices)
        if last_good != resids_clean[-1]:
            print(f"  [{seg.segid}] Stripped incomplete terminal residue(s) after resid {last_good}")

    u.atoms[keep_indices].write(output_pdb)


def mark_disulfides(pdb):
    """
    Detect disulfide bonds by SG-SG distance (< 2.5 Å), rename both CYS -> CYX
    in place, and rewrite the PDB. tLEaP applies an HG hydrogen to plain CYS,
    which produces "No torsion terms for HS-SH-SH-HS" errors on bonded cysteines.
    Returns the disulfide pairs in the file's residue numbering so the caller
    can emit tLEaP `bond` commands.
    """
    import MDAnalysis as mda
    import numpy as np
    import warnings
    warnings.filterwarnings("ignore")

    u = mda.Universe(pdb)
    sg = u.select_atoms("resname CYS CYX and name SG")
    pairs = []
    for i in range(len(sg)):
        for j in range(i + 1, len(sg)):
            if np.linalg.norm(sg[i].position - sg[j].position) < 2.5:
                sg[i].residue.resname = "CYX"
                sg[j].residue.resname = "CYX"
                pairs.append((sg[i].residue.resid, sg[j].residue.resid))

    if pairs:
        u.atoms.write(pdb)
        print(f"  Detected {len(pairs)} disulfide bond(s) — renamed CYS -> CYX")
        print("  tLEaP bond commands (final numbering):")
        for a, b in pairs:
            print(f"    bond mol.{a}.SG mol.{b}.SG")
    return pairs


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python cap_protein.py input.pdb output_capped.pdb")
        sys.exit(1)

    input_pdb  = sys.argv[1]
    output_pdb = sys.argv[2]

    # Step 1: strip incomplete terminal residues into a temp file
    with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as tmp:
        tmp_pdb = tmp.name

    try:
        strip_incomplete_termini(input_pdb, tmp_pdb)

        # Step 2: run add_caps.py
        result = subprocess.run(
            [sys.executable, ADD_CAPS, "-i", tmp_pdb, "-o", output_pdb],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"add_caps.py failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(result.returncode)

    finally:
        if os.path.exists(tmp_pdb):
            os.unlink(tmp_pdb)

    # Step 3: auto-detect disulfides and rename CYS -> CYX in the capped PDB
    mark_disulfides(output_pdb)

    with open(output_pdb) as f:
        n_lines = sum(1 for l in f if l.startswith("ATOM"))
    print(f"Wrote capped PDB: {output_pdb}  ({n_lines} atoms)")

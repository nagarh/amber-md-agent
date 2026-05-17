"""Prep protein_protonated.pdb for tleap:
- Rename SS-bonded CYS -> CYX
- Build sequential residue index mapping for tleap `bond` commands
- Emit tleap bond lines
"""

inp = "studies/trypsin_benzamidine/system/protein_protonated.pdb"
out = "studies/trypsin_benzamidine/system/protein_tleap.pdb"

# SSBOND pairs (PDB residue numbers)
SS_PAIRS = [(22, 157), (42, 58), (128, 232), (136, 201), (168, 182), (191, 220)]
ss_residues = set()
for a, b in SS_PAIRS:
    ss_residues.add(a)
    ss_residues.add(b)

# Pass 1: collect residue order (unique PDB resnums in file order)
seen = []
seen_set = set()
lines = open(inp).readlines()
for l in lines:
    if l.startswith("ATOM"):
        rn = int(l[22:26])
        if rn not in seen_set:
            seen.append(rn)
            seen_set.add(rn)

# tleap idx = position in sequence (1-based)
pdb_to_idx = {rn: i + 1 for i, rn in enumerate(seen)}

# Pass 2: rename CYS->CYX at SS positions
new = []
renamed = 0
for l in lines:
    if l.startswith("ATOM") and l[17:20].strip() == "CYS":
        rn = int(l[22:26])
        if rn in ss_residues:
            l = l[:17] + "CYX" + l[20:]
            renamed += 1
    new.append(l)
open(out, "w").writelines(new)
print(f"Wrote {out}  CYX atoms renamed: {renamed}")

# Emit tleap bond commands
print("\nTleap bond commands (use these in tleap script):")
for a, b in SS_PAIRS:
    ia, ib = pdb_to_idx[a], pdb_to_idx[b]
    print(f"bond prot.{ia}.SG prot.{ib}.SG    # CYX A {a} (idx {ia}) <-> CYX A {b} (idx {ib})")

# Find Asp189 internal index (we need this for restraint mask later)
print(f"\nAsp189 -> tleap idx {pdb_to_idx.get(189)}")
print(f"Ile16  -> tleap idx {pdb_to_idx.get(16)}  (mature N-term)")
print(f"N residues total: {len(seen)}")

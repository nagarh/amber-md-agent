"""Inspect built prmtop: counts, atom indices for restraint masks."""
import parmed as pmd

p = pmd.load_file(
    "studies/trypsin_benzamidine/system/system.prmtop",
    "studies/trypsin_benzamidine/system/system.inpcrd",
)

print(f"Total atoms: {len(p.atoms)}")
print(f"Total residues: {len(p.residues)}")

# Count by residue category
counts = {}
for r in p.residues:
    counts[r.name] = counts.get(r.name, 0) + 1
prot_res = sum(c for n, c in counts.items() if n not in ("WAT", "Na+", "Cl-", "BEN", "CA"))
print(f"Protein residues: {prot_res}")
print(f"Water (WAT): {counts.get('WAT', 0)}")
print(f"Na+: {counts.get('Na+', 0)}  Cl-: {counts.get('Cl-', 0)}")
print(f"BEN: {counts.get('BEN', 0)}  CA: {counts.get('CA', 0)}")

# Net charge
net_charge = sum(a.charge for a in p.atoms)
print(f"Net charge: {net_charge:.6f}")

# Box dims
print(f"Box dims: {p.box}")

# Find BEN atoms (ligand)
ben_atoms = []
for r in p.residues:
    if r.name == "BEN":
        for a in r.atoms:
            ben_atoms.append((a.idx + 1, a.name))  # Amber 1-based
        break
print(f"\nBEN atoms (1-based for &rst iat):")
for idx, name in ben_atoms:
    print(f"  atom {idx}  name {name}")

# Find Asp residue - need ASP at position equivalent to PDB 189
# After pdb4amber renumber, ASP189 is at sequence position 169 (computed earlier)
print(f"\nLooking for Asp at sequence position 169 (was PDB 189):")
for r in p.residues:
    if r.number == 169 or (r.idx + 1 == 169):
        print(f"  Found: {r.name} idx {r.idx} number {r.number}")
        for a in r.atoms:
            if a.name == "CA":
                print(f"  CA atom: {a.idx + 1}  name {a.name}")

# Robust: find all ASP residues and pick the one matching pose
print("\nAll ASP residues:")
for r in p.residues:
    if r.name == "ASP":
        ca = next((a for a in r.atoms if a.name == "CA"), None)
        if ca:
            print(f"  ASP idx {r.idx} number {r.number}  CA atom {ca.idx + 1}  pos {ca.xx:.1f},{ca.xy:.1f},{ca.xz:.1f}")

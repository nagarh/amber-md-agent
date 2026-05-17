#!/usr/bin/env python3
"""
Mutate THR315 → ILE315 in ABL1 chain A.
Strategy: replace OG1/HG1 (Thr-unique) with ILE side chain geometry.
Uses PDB coordinate surgery — keeps all common atoms (N,CA,C,O,CB,CG2),
replaces Thr-unique OG1+HG1 with Ile-unique CG1+2H,CD1+3H.
Output PDB has ILE residue at 315 for tleap build.
"""
import math

# Thr315 atoms in 1IEP chain A (from grep):
#   N, CA, C, O, CB, OG1, CG2
# ILE atoms needed: N, CA, C, O, CB, CG1, CG2, CD1

# We'll:
# 1. Read protein_capped.pdb
# 2. At residue 315: drop OG1, HG1; insert CG1, HG11, HG12, CD1, HD11, HD12, HD13
# 3. Place new atoms using idealized ILE geometry from reference Ile residue in structure
# 4. Rename residue THR→ILE, write output

def read_pdb(path):
    atoms = []
    other = []
    with open(path) as f:
        for line in f:
            if line[:6].strip() in ('ATOM', 'HETATM'):
                atoms.append({
                    'line': line,
                    'rec': line[:6].strip(),
                    'serial': int(line[6:11]),
                    'name': line[12:16].strip(),
                    'altloc': line[16],
                    'resname': line[17:20].strip(),
                    'chain': line[21],
                    'resseq': int(line[22:26]),
                    'icode': line[26],
                    'x': float(line[30:38]),
                    'y': float(line[38:46]),
                    'z': float(line[46:54]),
                    'occupancy': line[54:60].strip(),
                    'bfactor': line[60:66].strip(),
                    'element': line[76:78].strip() if len(line) > 76 else '',
                })
            else:
                other.append(line)
    return atoms, other

def vec_add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vec_sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vec_scale(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def vec_norm(a):
    d = math.sqrt(sum(x*x for x in a))
    return (a[0]/d, a[1]/d, a[2]/d) if d > 1e-9 else (0,0,1)
def vec_dot(a, b): return sum(x*y for x,y in zip(a,b))
def vec_cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def place_atom(origin, direction, length):
    d = vec_norm(direction)
    return vec_add(origin, vec_scale(d, length))

def place_tetrahedral(center, bonded_neighbors, bond_length):
    """Place new atom tetrahedrally from center given existing bonded neighbors."""
    # Sum of unit vectors from center to neighbors
    sv = [0.0, 0.0, 0.0]
    for n in bonded_neighbors:
        v = vec_norm(vec_sub(n, center))
        sv = [sv[i]+v[i] for i in range(3)]
    # New atom is in direction opposite to sum
    direction = vec_norm(tuple(-sv[i] for i in range(3)))
    return vec_add(center, vec_scale(direction, bond_length))

def atom_pos(atoms, resseq, name):
    for a in atoms:
        if a['resseq'] == resseq and a['name'] == name and a['chain'] == 'A':
            return (a['x'], a['y'], a['z'])
    return None

def write_atom(serial, name, resname, chain, resseq, x, y, z, elem):
    return (f"ATOM  {serial:5d} {name:<4s} {resname:<3s} {chain}{resseq:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 30.00          {elem:>2s}  \n")

def main():
    infile  = "studies/ABL1_T315I_imatinib_TI/system/protein_capped.pdb"
    outfile = "studies/ABL1_T315I_imatinib_TI/system/protein_T315I.pdb"

    atoms, other = read_pdb(infile)

    # T315 → residue 92 in capped PDB (offset: original - 223)
    RES = 92
    n315   = atom_pos(atoms, RES, 'N')
    ca315  = atom_pos(atoms, RES, 'CA')
    cb315  = atom_pos(atoms, RES, 'CB')
    cg2315 = atom_pos(atoms, RES, 'CG2')
    og1315 = atom_pos(atoms, RES, 'OG1')

    if not all([n315, ca315, cb315, cg2315, og1315]):
        raise ValueError(f"Could not find all T315 atoms at renumbered residue {RES}")

    # Place ILE CG1: tetrahedral from CB, neighbors are CA and CG2
    # CB is bonded to: N (backbone CA), CG1, CG2 in ILE
    # Use CA, CG2 as existing bonds, place CG1 tetrahedrally
    cg1_pos = place_tetrahedral(cb315, [ca315, cg2315, n315], 1.53)

    # Place CD1 along CG1 direction from CB
    # CD1 is bonded to CG1; direction = extension of CB→CG1 with sp3 angle (~111°)
    # Simple: place CD1 in direction away from CB, at sp3 angle from CB-CG1
    cb_cg1 = vec_sub(cg1_pos, cb315)
    # Perpendicular component using CG2 as reference
    cb_cg2 = vec_norm(vec_sub(cg2315, cb315))
    cb_cg1_n = vec_norm(cb_cg1)
    # CD1 extension: tetrahedral from CG1, neighbors CB
    # For CD1, place away from CB
    cd1_pos = place_tetrahedral(cg1_pos, [cb315], 1.53)

    # Place H atoms (1.09 Å from parent C)
    # HG11, HG12 on CG1 (tetrahedral, neighbors: CB, CD1)
    hg11_pos = place_tetrahedral(cg1_pos, [cb315, cd1_pos], 1.09)
    # HG12: perpendicular to HG11 plane
    # Use cross product for second H
    v1 = vec_norm(vec_sub(cb315, cg1_pos))
    v2 = vec_norm(vec_sub(cd1_pos, cg1_pos))
    perp = vec_norm(vec_cross(v1, v2))
    # Place second H at tetrahedral angle (~109.5°)
    mid = vec_norm((v1[0]+v2[0], v1[1]+v2[1], v1[2]+v2[2]))
    # HG12 direction: mid rotated 120° around (v1+v2) axis — approximate with perp component
    h_dir = vec_norm(vec_add(vec_scale(mid, -0.333), vec_scale(perp, 0.943)))
    hg12_pos = vec_add(cg1_pos, vec_scale(h_dir, 1.09))

    # HD1x on CD1 (3 hydrogens, methyl)
    cd1_dir = vec_norm(vec_sub(cd1_pos, cg1_pos))
    # Use 3-fold symmetry around CD1-CG1 axis
    # First H: tetrahedral from CD1 pointing away from CG1
    hd11_pos = place_tetrahedral(cd1_pos, [cg1_pos], 1.09)
    perp2 = vec_norm(vec_cross(cd1_dir, (0,1,0) if abs(cd1_dir[1]) < 0.9 else (1,0,0)))
    cos_t = math.cos(math.radians(109.5))
    sin_t = math.sin(math.radians(109.5))
    neg_dir = vec_scale(cd1_dir, -cos_t)
    hd12_pos = vec_add(cd1_pos, vec_scale(
        vec_add(neg_dir, vec_scale(perp2, sin_t)), 1.09))
    perp3 = vec_norm(vec_cross(cd1_dir, perp2))
    hd13_pos = vec_add(cd1_pos, vec_scale(
        vec_add(neg_dir, vec_scale(
            vec_add(vec_scale(perp2, -0.5), vec_scale(perp3, 0.866)), sin_t)), 1.09))

    # Build output atom list
    out_atoms = []
    serial = 1
    skip_names = {'OG1', 'HG1', '1HG1', '2HG1'}  # Thr-unique, remove

    for a in atoms:
        if a['chain'] == 'A' and a['resseq'] == RES:
            if a['name'] in skip_names or (a['name'].startswith('HG1') and len(a['name']) <= 3):
                continue  # drop Thr-unique atoms
            if a['name'] == 'OG1':
                continue
            # Rename residue
            a = dict(a)
            a['resname'] = 'ILE'

        # Write atom
        x, y, z = a['x'], a['y'], a['z']
        elem = a.get('element', a['name'][0])
        out_atoms.append(write_atom(serial, a['name'], a['resname'],
                                     a['chain'], a['resseq'], x, y, z, elem))
        serial += 1

        # After CB of residue 92 (T315I), insert ILE-unique atoms
        if a['chain'] == 'A' and a.get('resseq') == RES and a['name'] == 'CB':
            new_atoms_315 = [
                ('CG1',  cg1_pos,  'C'),
                ('HG12', hg11_pos, 'H'),
                ('HG13', hg12_pos, 'H'),
                ('CD1',  cd1_pos,  'C'),
                ('HD11', hd11_pos, 'H'),
                ('HD12', hd12_pos, 'H'),
                ('HD13', hd13_pos, 'H'),
            ]
            for atname, pos, elem in new_atoms_315:
                out_atoms.append(write_atom(serial, atname, 'ILE', 'A', RES,
                                             pos[0], pos[1], pos[2], elem))
                serial += 1

    with open(outfile, 'w') as f:
        f.writelines(out_atoms)
        f.write("END\n")

    print(f"Written: {outfile}  ({len(out_atoms)} ATOM lines)")
    # Report T315I atoms
    ile_atoms = [l for l in out_atoms if f'ILE A  {RES}' in l or f'ILE A {RES}' in l]
    print(f"ILE315 atoms: {len(ile_atoms)}")

if __name__ == '__main__':
    main()

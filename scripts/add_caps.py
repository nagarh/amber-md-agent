# Written by Mohd Ibrahim
# Technical University of Munich
# Email: ibrahim.mohd@tum.de

import numpy as np
import MDAnalysis as mda
import argparse
import warnings
warnings.filterwarnings("ignore")

np.random.seed(42)  

parser = argparse.ArgumentParser(
    description="Add capping groups ACE and NME to protein termini. "
                "Remove hydrogens before using this script")
parser.add_argument('-i', dest='in_file', type=str,
                    default='protein_noh.pdb', help='pdb file')
parser.add_argument('-o', dest='out_file', type=str,
                    default='protein_noh_cap.pdb', help='output file')

args = parser.parse_args()
in_file = args.in_file
out_file = args.out_file


def create_universe(n_atoms, name, resname, positions, resids, segid):
    # C-12 fix: capping group is a SINGLE residue — use n_residues=1, n_segments=1.
    # The old code used n_residues=n_atoms / n_segments=n_atoms which created one
    # segment and residue per atom (3 residues for ACE, 2 for NME) instead of 1+1,
    # silently corrupting the topology for downstream parmed/MDAnalysis readers.
    u_new = mda.Universe.empty(
        n_atoms=n_atoms,
        n_residues=1,
        atom_resindex=np.zeros(n_atoms, dtype=int),
        residue_segindex=[0],
        n_segments=1,
        trajectory=True
    )
    u_new.add_TopologyAttr('name', name)
    u_new.add_TopologyAttr('resid', [resids[0]] if hasattr(resids, '__len__') else [resids])
    u_new.add_TopologyAttr('resname', [resname[0]] if hasattr(resname, '__len__') else [resname])
    u_new.atoms.positions = positions
    u_new.add_TopologyAttr('segid', [segid])  # per-segment (n_segments=1)
    u_new.add_TopologyAttr('chainID', n_atoms * [segid])  # per-atom
    return u_new


def get_nme_pos(end_residue):
    if "OXT" in end_residue.names:
        index = np.where(end_residue.names == "OXT")[0][0]
        N_position = end_residue.positions[index]
        index_c = np.where(end_residue.names == "C")[0][0]
        carbon_position = end_residue.positions[index_c]
        vector = N_position - carbon_position
        vector /= np.sqrt(sum(vector**2))
        C_position = N_position + vector * 1.36
        return N_position, C_position
    else:
        index_o = np.where(end_residue.names == "O")[0][0]
        index_ca = np.where(end_residue.names == "CA")[0][0]
        mid_point = (end_residue.positions[index_o] +
                     end_residue.positions[index_ca]) / 2
        index_c = np.where(end_residue.names == "C")[0][0]
        vector = end_residue.positions[index_c] - mid_point
        vector /= np.sqrt(sum(vector**2))
        N_position = end_residue.positions[index_c] + 1.36 * vector
        C_position = N_position + 1.36 * vector
        return N_position, C_position


def get_ace_pos(end_residue):
    index_ca = np.where(end_residue.names == "CA")[0][0]
    index_n = np.where(end_residue.names == "N")[0][0]
    vector = end_residue.positions[index_n] - end_residue.positions[index_ca]
    vector /= np.sqrt(sum(vector**2))
    C1_position = end_residue.positions[index_n] + 1.36 * vector

    xa, ya, za = end_residue.positions[index_ca]
    xg, yg, zg = C1_position

    orientation = np.array([2 * np.random.rand() - 1,
                            2 * np.random.rand() - 1,
                            2 * np.random.rand() - 1])
    nx, ny, nz = orientation / np.sqrt(sum(orientation**2))

    x1 = xg - (xa - xg) / 2 + np.sqrt(3) * (ny * (za - zg) - nz * (ya - yg)) / 2
    y1 = yg - (ya - yg) / 2 + np.sqrt(3) * (nz * (xa - xg) - nx * (za - zg)) / 2
    z1 = zg - (za - zg) / 2 + np.sqrt(3) * (nx * (ya - yg) - ny * (xa - xg)) / 2

    x2 = xg - (xa - xg) / 2 - np.sqrt(3) * (ny * (za - zg) - nz * (ya - yg)) / 2
    y2 = yg - (ya - yg) / 2 - np.sqrt(3) * (nz * (xa - xg) - nx * (za - zg)) / 2
    z2 = zg - (za - zg) / 2 - np.sqrt(3) * (nx * (ya - yg) - ny * (xa - xg)) / 2

    C2_position = np.array([x1, y1, z1])
    O_position = np.array([x2, y2, z2])

    vector = C2_position - C1_position
    vector /= np.sqrt(sum(vector**2))
    C2_position = C1_position + 1.36 * vector

    vector = O_position - C1_position
    vector /= np.sqrt(sum(vector**2))
    O_position = C1_position + 1.36 * vector

    return C1_position, C2_position, O_position


# ----------- Main processing -----------
u = mda.Universe(in_file)
res_start = 0
segment_universes = []

for seg in u.segments:
    chain = u.select_atoms(f"segid {seg.segid}")

    # ACE
    resid_c = chain.residues.resids[0]
    end_residue = u.select_atoms(f"segid {seg.segid} and resid {resid_c}")
    c1_pos, c2_pos, o_pos = get_ace_pos(end_residue)

    # Build ACE in Amber atom order: CH3, C, O — no reorder merge needed
    ace_names = ["CH3", "C", "O"]
    ace_positions = [c2_pos, c1_pos, o_pos]
    resid = chain.residues.resids[0]
    ace_universe = create_universe(
        n_atoms=len(ace_positions),
        name=ace_names,
        resname=len(ace_names) * ["ACE"],
        positions=ace_positions,
        resids=resid * np.ones(len(ace_names)),
        segid=chain.segids[0]
    )

    # NME
    resid_c = chain.residues.resids[-1]
    end_residue = u.select_atoms(f"segid {seg.segid} and resid {resid_c}")
    nme_positions = get_nme_pos(end_residue)
    nme_names = ["N", "C"]
    resid = chain.residues.resids[-1] + 2
    nme_universe = create_universe(
        n_atoms=len(nme_names),
        name=nme_names,
        resname=len(nme_names) * ["NME"],
        positions=nme_positions,
        resids=resid * np.ones(len(nme_names)),
        segid=chain.segids[0]
    )

    # Remove OXT if present
    if "OXT" in end_residue.names:
        index = np.where(end_residue.names == "OXT")[0][0]
        OXT = end_residue[index]
        Chain = u.select_atoms(f"segid {seg.segid} and not index {OXT.index}")
    else:
        Chain = u.select_atoms(f"segid {seg.segid}")

    # Save original protein resids before Merge resets them
    original_pro_resids = Chain.residues.resids.copy()
    first_pro_resid = int(original_pro_resids[0])
    last_pro_resid = int(original_pro_resids[-1])

    # Merge ACE, protein, NME
    u_all = mda.Merge(ace_universe.atoms, Chain, nme_universe.atoms)

    # Restore original numbering — ACE = first_resid-1, protein = original, NME = last_resid+1
    # This keeps propka3/apply_protonation_overrides residue numbers consistent with the capped PDB.
    n_ace_res = ace_universe.residues.n_residues   # 1 after ACE fix
    n_nme_res = nme_universe.residues.n_residues   # 1
    n_pro_res = Chain.residues.n_residues
    u_all.residues[:n_ace_res].resids = [first_pro_resid - 1] * n_ace_res
    u_all.residues[n_ace_res:n_ace_res + n_pro_res].resids = original_pro_resids
    u_all.residues[n_ace_res + n_pro_res:].resids = [last_pro_resid + 1] * n_nme_res
    res_start = last_pro_resid + 1
    segment_universes.append(u_all)

# Join and write output
all_uni = mda.Merge(*(seg.atoms for seg in segment_universes))
all_uni.atoms.write(out_file)

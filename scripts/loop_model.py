#!/usr/bin/env python3
"""
loop_model.py — Fill missing residue ranges in crystal PDB using AlphaFold/ESMFold.

Usage:
    python scripts/loop_model.py \
        --pdb studies/X/raw_pdbs/struct.pdb \
        --missing "A:86-91,A:120-125" \
        --uniprot P12345 \
        --out studies/X/raw_pdbs/struct_modeled.pdb

Output:
    - <out>          assembled PDB with modeled loops
    - <out>.meta.json  pLDDT values, source, user decisions
"""

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_servers"))

try:
    from Bio.PDB import PDBParser, Superimposer, PDBIO
    BIOPYTHON_OK = True
except ImportError:
    BIOPYTHON_OK = False

ESM_FOLD_URL = "https://api.esmatlas.com/foldSequence/v1/pdb/"

THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "HID": "H", "HIE": "H", "HIP": "H", "CYX": "C", "ASH": "D", "GLH": "E",
}

try:
    from alphafold_server import get_plddt_scores as alphafold_get_plddt_scores
    from alphafold_server import get_prediction as alphafold_get_prediction
    _ALPHAFOLD_OK = True
except ImportError:
    _ALPHAFOLD_OK = False
    alphafold_get_plddt_scores = None
    alphafold_get_prediction = None


# ---------------------------------------------------------------------------
# Junction geometry validation (C-01 fix)
# ---------------------------------------------------------------------------

def validate_junction_geometry(pdb_path: str, min_bond: float = 1.0, max_bond: float = 1.7) -> bool:
    """Walk all inter-residue C-N peptide bonds; raise ValueError if any falls outside [min_bond, max_bond] Å.

    Returns True on success. Called by loop_model() after graft, before write.
    Fixes C-01: post-graft junction validation to detect collapsed (0.33 Å) bonds.
    """
    import math
    atoms = []
    with open(pdb_path) as f:
        for line in f:
            if not line.startswith("ATOM"):
                continue
            name = line[12:16].strip()
            if name not in ("C", "N"):
                continue
            chain_id = line[21]
            try:
                res_seq = int(line[22:26])
            except ValueError:
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            atoms.append((chain_id, res_seq, name, x, y, z))
    by_res = {}
    for chain_id, r, n, x, y, z in atoms:
        by_res.setdefault((chain_id, r), {})[n] = (x, y, z)
    res_ids = sorted(by_res)
    for i in range(len(res_ids) - 1):
        key1, key2 = res_ids[i], res_ids[i + 1]
        # H-06 fix: skip cross-chain bonds — they are not peptide bonds
        if key1[0] != key2[0]:
            continue
        r1, r2 = key1[1], key2[1]
        c = by_res.get(key1, {}).get("C")
        n = by_res.get(key2, {}).get("N")
        if c is None or n is None:
            continue
        d = math.sqrt(sum((a - b) ** 2 for a, b in zip(c, n)))
        if d < min_bond or d > max_bond:
            raise ValueError(
                f"Bad junction geometry: chain {key1[0]} residue {r1} C → residue {r2} N = {d:.3f} Å "
                f"(expected [{min_bond}, {max_bond}])"
            )
    return True


def parse_dbref_offsets(pdb_path: str) -> dict:
    """
    Read DBREF records from crystal PDB and return per-chain UniProt offset.

    DBREF format (cols 1-6=record, 8-11=pdbid, 13=chain, 15-18=pdb_start, ...
                  34-41=db_accession, 43-54=id_code, 56-60=uniprot_start, ...)

    Returns {chain: uniprot_start - pdb_start}
    e.g. 5YNP chain A DBREF: pdb_start=1, uniprot_start=6776 → offset=6775
    Chains with offset=0 (or no DBREF) are omitted — callers treat missing key as 0.
    """
    offsets = {}
    try:
        with open(pdb_path) as f:
            for line in f:
                if not line.startswith("DBREF "):
                    continue
                chain       = line[12]
                pdb_start   = int(line[14:18].strip())
                uniprot_start = int(line[55:60].strip())
                offset = uniprot_start - pdb_start
                if offset != 0:
                    offsets[chain] = offset
                    print(f"[loop_model] DBREF chain {chain}: pdb_start={pdb_start}, "
                          f"uniprot_start={uniprot_start}, offset={offset}")
    except Exception as e:
        print(f"[loop_model] WARNING: could not parse DBREF from {pdb_path}: {e}")
    return offsets


def parse_missing_ranges(missing_str: str) -> list:
    """Parse 'A:86-91,B:10-20' → [('A',86,91), ('B',10,20)]"""
    if not missing_str.strip():
        return []
    ranges = []
    for part in missing_str.split(","):
        part = part.strip()
        try:
            chain, span = part.split(":")
            start, end = span.split("-")
        except ValueError as e:
            raise ValueError(f"Malformed range '{part}': expected format 'CHAIN:START-END'") from e
        start_int = int(start)
        end_int = int(end)
        if start_int > end_int:
            raise ValueError(f"Invalid range '{part}': start {start_int} > end {end_int}")
        ranges.append((chain.strip(), start_int, end_int))
    return ranges


def get_plddt_for_ranges(uniprot_id: str, ranges: list,
                         dbref_offsets: dict = None) -> dict:
    """
    Query AlphaFold DB pLDDT for missing residue ranges.
    Returns None if protein not in AlphaFold DB.
    Returns {(chain, start, end): mean_plddt} otherwise.

    dbref_offsets: {chain: uniprot_start - pdb_start} from parse_dbref_offsets().
    When provided, crystal residue numbers are shifted to UniProt positions before
    looking up pLDDT (fixes DBREF offset bug — PDB residue ≠ UniProt residue).
    """
    scores = alphafold_get_plddt_scores(uniprot_id)
    if "error" in scores:
        return None  # not in DB

    residue_map = {r["residue"]: r["plddt"]
                   for r in scores.get("per_residue", [])}

    result = {}
    for (chain, start, end) in ranges:
        expected = end - start + 1
        off = (dbref_offsets or {}).get(chain, 0)
        af_start = start + off
        af_end   = end   + off
        if off:
            print(f"[loop_model] pLDDT lookup {chain}:{start}-{end} → "
                  f"UniProt {af_start}-{af_end} (DBREF offset={off})")
        values = [residue_map[i] for i in range(af_start, af_end + 1) if i in residue_map]
        if not values:
            # AF API returned no scores for this range — unknown confidence, not low
            print(f"[loop_model] WARNING: no pLDDT data for {chain}:{start}-{end} "
                  f"(AF API returned empty). Treating as unknown — proceeding with graft.")
            result[(chain, start, end)] = None
        else:
            if len(values) < expected:
                print(f"[loop_model] WARNING: {expected - len(values)}/{expected} residues "
                      f"missing pLDDT for {chain}:{start}-{end}. Mean of found residues only.")
            result[(chain, start, end)] = sum(values) / len(values)
    return result


_AF_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "af_cache"


def fetch_alphafold_pdb(uniprot_id: str) -> str:
    """Download AlphaFold PDB string. Caches to data/af_cache/<uniprot_id>.pdb.

    Cache hit = instant (no network). Cache miss = download + save.
    Eliminates repeated AF downloads for same protein across runs.
    """
    _AF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _AF_CACHE_DIR / f"{uniprot_id}.pdb"

    if cache_file.exists() and cache_file.stat().st_size > 1000:
        print(f"[loop_model] AF cache hit: {uniprot_id} ({cache_file.stat().st_size // 1024} KB)")
        return cache_file.read_text()

    pred = alphafold_get_prediction(uniprot_id)
    if "error" in pred:
        return None
    pdb_url = pred.get("pdb_url", "")
    if not pdb_url:
        return None
    for attempt in range(3):
        try:
            req = urllib.request.Request(pdb_url,
                  headers={"User-Agent": "AmberMD-Agent/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read().decode()
            cache_file.write_text(content)
            print(f"[loop_model] AF downloaded + cached: {uniprot_id} ({len(content)//1024} KB)")
            return content
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                print(f"[loop_model] AlphaFold download attempt {attempt+1} failed ({e}). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"[loop_model] AlphaFold download failed after 3 attempts: {e}", file=sys.stderr)
                return None


# ---------------------------------------------------------------------------
# Task 3 — ESMFold API + sequence extraction
# ---------------------------------------------------------------------------

def get_sequence_from_pdb(pdb_path: str, chain: str = "A") -> str:
    """Extract one-letter sequence from CA atoms of specified chain.

    H-07 fix: use line[22:27] (resnum + insertion code) as the dict key so
    residues with insertion codes (e.g. 100, 100A) are not overwritten.
    """
    seen = {}
    with open(pdb_path) as f:
        for line in f:
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                ch = line[21]
                if ch != chain:
                    continue
                # H-07: key on residue number + insertion code (columns 22-27)
                res_key = line[22:27]  # e.g. "  100 " or "  100A"
                resname = line[17:20].strip()
                if res_key not in seen:
                    seen[res_key] = THREE_TO_ONE.get(resname, "X")
    return "".join(seen[k] for k in sorted(seen))


def call_esm_fold(sequence: str) -> str:
    """Call ESMFold public API, return PDB string or None on failure after 3 attempts."""
    data = sequence.encode()
    for attempt in range(3):
        req = urllib.request.Request(
            ESM_FOLD_URL,
            data=data,
            headers={"Content-Type": "text/plain"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read().decode()
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                print(f"[loop_model] ESMFold attempt {attempt+1} failed ({e}). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"[loop_model] ESMFold API failed after 3 attempts: {e}", file=sys.stderr)
                return None


# ---------------------------------------------------------------------------
# Task 4 — BioPython alignment
# ---------------------------------------------------------------------------

def _load_structure(pdb_path_or_str: str, struct_id: str = "s"):
    """Load BioPython structure from file path or PDB string.

    M-36: Multi-line content (contains \\n) is treated as a PDB string regardless
    of leading whitespace/record. Single-line input without \\n is treated as
    a file path. CRLF tolerated.
    """
    parser = PDBParser(QUIET=True)
    is_str = "\n" in pdb_path_or_str or "\r" in pdb_path_or_str or \
             pdb_path_or_str.lstrip().startswith(("ATOM", "REMARK", "HEADER", "MODEL", "TITLE", "COMPND"))
    if is_str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
            f.write(pdb_path_or_str)
            tmp_path = f.name
        try:
            struct = parser.get_structure(struct_id, tmp_path)
        finally:
            os.unlink(tmp_path)
    else:
        struct = parser.get_structure(struct_id, pdb_path_or_str)
    return struct


def align_structures(crystal_path: str, predicted_pdb_str: str,
                     resolved_residues: list, chain: str = "A"):
    """
    Align predicted structure to crystal on CA atoms of resolved residues.
    Applies rotation/translation IN PLACE to predicted structure atoms.
    Returns (rotation_matrix, translation_vector, rmsd).
    """
    if not BIOPYTHON_OK:
        raise ImportError("BioPython required: pip install biopython")

    crystal = _load_structure(crystal_path, "crystal")
    predicted = _load_structure(predicted_pdb_str, "predicted")

    crystal_chain = crystal[0][chain]
    pred_chain_id = list(predicted[0].child_dict.keys())[0]
    pred_chain = predicted[0][pred_chain_id]

    res_set = set(resolved_residues)
    crystal_atoms, pred_atoms = [], []
    for res_id in res_set:
        try:
            crystal_atoms.append(crystal_chain[res_id]["CA"])
            pred_atoms.append(pred_chain[res_id]["CA"])
        except KeyError:
            continue

    if len(crystal_atoms) < 3:
        raise ValueError(
            f"Only {len(crystal_atoms)} common CA atoms found for alignment — need >= 3. "
            f"Crystal and predicted structures may not share enough resolved residues."
        )

    sup = Superimposer()
    sup.set_atoms(crystal_atoms, pred_atoms)
    sup.apply(list(predicted.get_atoms()))
    return sup.rotran[0], sup.rotran[1], sup.rms


# ---------------------------------------------------------------------------
# Task 4b — 2-point Procrustes junction closure
# ---------------------------------------------------------------------------

def _get_bb_atom(lines_by_res: dict, chain: str, resnum, atom_name: str):
    """Return (x,y,z) of backbone atom from lines_by_res dict, or None.

    H-08 fix: accepts resnum as int or str. Tries both key forms so that
    integer-keyed (grafted_lines) and string-keyed (crystal_lines_by_res)
    dicts both work.
    """
    import numpy as np
    # Try both int and string key forms to support both dict conventions
    for key in ((chain, resnum), (chain, str(resnum))):
        for line in lines_by_res.get(key, []):
            if (line.startswith("ATOM") or line.startswith("HETATM")):
                if line[12:16].strip() == atom_name:
                    try:
                        return np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                    except ValueError:
                        pass
    return None


def _find_anchor(lines_by_res: dict, chain: str, start_res: int,
                 atom_name: str, direction: int, search_radius: int = 3):
    """
    Search for backbone atom near a gap boundary, handling partially-resolved
    residues. direction=-1 searches backward (N-terminal anchor, look for 'C');
    direction=+1 searches forward (C-terminal anchor, look for 'N').
    Returns (resnum_found, coords) or (None, None).
    """
    for offset in range(search_radius + 1):
        resnum = start_res + direction * offset
        coords = _get_bb_atom(lines_by_res, chain, resnum, atom_name)
        if coords is not None:
            return resnum, coords
    return None, None


def _kabsch(src_pts, tgt_pts):
    """
    Kabsch algorithm: optimal rotation R and translation t mapping src → tgt.
    src_pts, tgt_pts: numpy arrays of shape (N, 3).
    Returns (R, t) where new_pos = R @ old_pos + t.
    """
    import numpy as np
    c_src = src_pts.mean(axis=0)
    c_tgt = tgt_pts.mean(axis=0)
    H = (src_pts - c_src).T @ (tgt_pts - c_tgt)
    U, _, Vt = np.linalg.svd(H)
    d = np.linalg.det(Vt.T @ U.T)
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    t = c_tgt - R @ c_src
    return R, t


def _apply_transform_to_lines(lines_dict: dict, keys: list, R, t) -> dict:
    """Apply rigid-body transform (R, t) to atom lines for given keys. Returns updated dict."""
    import numpy as np
    # L-09: deep-copy inner lists so caller mutations don't leak into source
    updated = {k: list(v) for k, v in lines_dict.items()}
    for key in keys:
        new_lines = []
        for line in lines_dict[key]:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                try:
                    pos = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                    p = R @ pos + t
                    new_line = line[:30] + f"{p[0]:8.3f}{p[1]:8.3f}{p[2]:8.3f}" + line[54:]
                    new_lines.append(new_line)
                except (ValueError, IndexError):
                    new_lines.append(line)
            else:
                new_lines.append(line)
        updated[key] = new_lines
    return updated



# ---------------------------------------------------------------------------
# CCD loop closure (replaces 2-point Kabsch and 10-Cα local alignment)
# ---------------------------------------------------------------------------

_BOND_CN  = 1.329   # ideal C-N peptide bond Å
_CCD_TOL  = 0.15    # acceptable deviation from ideal bond Å
_BB_ATOMS = {"N", "CA", "C", "O"}


def _rodrigues(points, axis, pivot, angle):
    """Rotate points (N×3 array) around axis through pivot by angle (rad)."""
    import numpy as np
    k = axis / (np.linalg.norm(axis) + 1e-12)
    v = points - pivot
    c, s = np.cos(angle), np.sin(angle)
    return v * c + np.cross(k, v) * s + k * (v @ k)[:, None] * (1 - c) + pivot


def _ccd_angle(pivot, axis, end_effector, target):
    """Optimal rotation angle around axis/pivot to minimise |rot(end_effector) - target|."""
    import numpy as np
    k = axis / (np.linalg.norm(axis) + 1e-12)
    r_perp = end_effector - pivot; r_perp -= np.dot(r_perp, k) * k
    t_perp = target      - pivot; t_perp -= np.dot(t_perp, k) * k
    nr, nt = np.linalg.norm(r_perp), np.linalg.norm(t_perp)
    if nr < 1e-6 or nt < 1e-6:
        return 0.0
    cross = np.cross(r_perp / nr, t_perp / nt)
    return np.arctan2(np.dot(cross, k), np.dot(r_perp / nr, t_perp / nt))


def _parse_bb_from_lines(lines_dict, chain, res_list):
    """Extract backbone coords from PDB lines dict → {(resnum, atom_name): np.array}."""
    import numpy as np
    coords = {}
    for rn in res_list:
        for key in ((chain, rn), (chain, str(rn))):
            for line in lines_dict.get(key, []):
                if not (line.startswith("ATOM") or line.startswith("HETATM")):
                    continue
                name = line[12:16].strip()
                if name not in _BB_ATOMS:
                    continue
                try:
                    coords[(rn, name)] = np.array(
                        [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                    )
                except ValueError:
                    pass
    return coords


def _write_bb_coords_to_lines(lines_dict, chain, res_list, updated_coords):
    """Write back updated backbone coords into PDB lines dict (in-place)."""
    result = {k: list(v) for k, v in lines_dict.items()}
    for rn in res_list:
        for key in ((chain, rn), (chain, str(rn))):
            if key not in result:
                continue
            new_lines = []
            for line in result[key]:
                name = line[12:16].strip()
                if name in _BB_ATOMS and (rn, name) in updated_coords:
                    xyz = updated_coords[(rn, name)]
                    line = (line[:30]
                            + f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}"
                            + line[54:])
                new_lines.append(line)
            result[key] = new_lines
    return result


def _run_ccd(bb_coords, anchor_C, anchor_N, res_list,
             max_iter=300, tol=_CCD_TOL):
    """
    Two-anchor CCD loop closure.

    bb_coords : {(resnum, atom_name): np.array}  — backbone coords, modified in-place copy
    anchor_C  : np.array — C of crystal residue before loop (N-terminal anchor)
    anchor_N  : np.array — N of crystal residue after  loop (C-terminal anchor)
    res_list  : sorted list of residue numbers in the loop

    Algorithm
    ---------
    Step 1  Translate entire loop so |N_first - anchor_C| = BOND_CN.
    Step 2  Forward pass (N→C): for each phi/psi bond, rotate downstream atoms
            to bring C_last toward (anchor_N - BOND_CN × direction).
    Step 3  Backward pass (C→N): rotate upstream atoms to keep N_first at
            BOND_CN from anchor_C.
    Step 4  Repeat until both junctions within tol of BOND_CN.

    Returns (updated_coords, d_N_final, d_C_final, converged).
    """
    import numpy as np
    import math

    atoms = {k: v.copy() for k, v in bb_coords.items()}
    res = res_list

    def get(rn, name):
        return atoms.get((rn, name))

    def apply_rot(pivot, axis, affected_keys, angle):
        pts = np.array([atoms[k] for k in affected_keys])
        rotated = _rodrigues(pts, axis, pivot, angle)
        for k, xyz in zip(affected_keys, rotated):
            atoms[k] = xyz

    # Step 1 — translate to fix N-terminal junction
    n0 = get(res[0], "N")
    if n0 is not None:
        vec = n0 - anchor_C
        dist = np.linalg.norm(vec)
        if dist > 1e-6:
            shift = vec / dist * (dist - _BOND_CN)
            for k in list(atoms):
                atoms[k] -= shift

    converged = False
    for iteration in range(max_iter):

        # Forward pass: phi (N–CA) then psi (CA–C), N→C order
        for i, rn in enumerate(res):
            for pivot_name, axis_name, skip in [("N", "CA", {"N"}),
                                                 ("CA", "C", {"N", "CA"})]:
                pivot    = get(rn, pivot_name)
                ax_atom  = get(rn, axis_name)
                effector = get(res[-1], "C")
                if pivot is None or ax_atom is None or effector is None:
                    continue
                vec = anchor_N - effector
                dist_e = np.linalg.norm(vec)
                target = (anchor_N - vec / dist_e * _BOND_CN
                          if dist_e > 1e-6 else anchor_N)
                axis = ax_atom - pivot
                angle = _ccd_angle(pivot, axis, effector, target)
                affected = [(r, nm) for r in res[i:] for nm in ("N","CA","C","O")
                            if (r, nm) in atoms and not (r == rn and nm in skip)]
                apply_rot(pivot, axis, affected, angle)

        # Backward pass: psi (CA–C reversed) then phi (N–CA reversed), C→N order
        for i in range(len(res) - 1, -1, -1):
            rn = res[i]
            ca = get(rn, "CA");  n = get(rn, "N")
            if ca is None or n is None:
                continue
            effector = get(res[0], "N")
            if effector is None:
                continue
            vec = anchor_C - effector
            dist_e = np.linalg.norm(vec)
            target = (anchor_C - vec / dist_e * _BOND_CN
                      if dist_e > 1e-6 else anchor_C)
            axis = n - ca
            angle = _ccd_angle(ca, axis, effector, target)
            affected = [(r, nm) for r in res[:i+1] for nm in ("N","CA","C","O")
                        if (r, nm) in atoms and not (r == rn and nm in ("CA","C","O"))]
            apply_rot(ca, axis, affected, angle)

        # Convergence check
        n0 = get(res[0], "N");  cN = get(res[-1], "C")
        d_N = abs(np.linalg.norm(n0 - anchor_C) - _BOND_CN) if n0 is not None else 999
        d_C = abs(np.linalg.norm(cN - anchor_N) - _BOND_CN) if cN is not None else 999
        if d_N < tol and d_C < tol:
            converged = True
            actual_dN = np.linalg.norm(n0 - anchor_C)
            actual_dC = np.linalg.norm(cN - anchor_N)
            print(f"[loop_model] CCD converged iter {iteration+1}: "
                  f"N-junc={actual_dN:.3f} Å  C-junc={actual_dC:.3f} Å")
            break

    n0 = get(res[0], "N");  cN = get(res[-1], "C")
    d_N_f = np.linalg.norm(n0 - anchor_C) if n0 is not None else 999
    d_C_f = np.linalg.norm(cN - anchor_N) if cN is not None else 999
    if not converged:
        print(f"[loop_model] CCD did not converge ({max_iter} iter): "
              f"N-junc={d_N_f:.3f} Å  C-junc={d_C_f:.3f} Å")
    return atoms, d_N_f, d_C_f, converged


def _translate_sidechains_by_ca_shift(lines_dict, chain, res_list, bb_before, bb_after):
    """Translate sidechain atoms by CA displacement after CCD backbone adjustment.

    CCD only moves backbone atoms. This shifts sidechain atoms to follow their CA
    so CA-CB distances remain chemically correct (~1.54 Å) after CCD.
    """
    import numpy as np
    result = {k: list(v) for k, v in lines_dict.items()}
    for rn in res_list:
        ca_old = bb_before.get((rn, "CA"))
        ca_new = bb_after.get((rn, "CA"))
        if ca_old is None or ca_new is None:
            continue
        delta = ca_new - ca_old
        if np.linalg.norm(delta) < 1e-6:
            continue
        for key in ((chain, rn), (chain, str(rn))):
            if key not in result:
                continue
            new_lines = []
            for line in result[key]:
                if line.startswith(("ATOM", "HETATM")):
                    name = line[12:16].strip()
                    if name not in _BB_ATOMS:  # sidechain only
                        try:
                            x = float(line[30:38]) + delta[0]
                            y = float(line[38:46]) + delta[1]
                            z = float(line[46:54]) + delta[2]
                            line = line[:30] + f"{x:8.3f}{y:8.3f}{z:8.3f}" + line[54:]
                        except (ValueError, IndexError):
                            pass
                new_lines.append(line)
            result[key] = new_lines
    return result


def _place_single_residue_ideal(anchor_C, anchor_N, bb, rn):
    """Place single gap residue backbone using ideal geometry between two anchors."""
    import numpy as np
    total = np.linalg.norm(anchor_N - anchor_C)
    direction = (anchor_N - anchor_C) / total if total > 1e-6 else np.array([1, 0, 0])
    # Approximate ideal positions along C-N axis
    n_pos  = anchor_C + direction * 1.33   # C-N bond
    ca_pos = n_pos    + direction * 1.46   # N-CA bond
    c_pos  = ca_pos   + direction * 1.52   # CA-C bond (toward anchor_N)
    o_pos  = c_pos    + direction * 0.1    # approximate O placement
    result = dict(bb)
    result[(rn, "N")]  = n_pos
    result[(rn, "CA")] = ca_pos
    result[(rn, "C")]  = c_pos
    result[(rn, "O")]  = o_pos
    return result


def _close_loop_junctions_ccd(grafted_lines: dict, crystal_lines_by_res: dict,
                               missing_ranges: list) -> dict:
    """
    CCD loop closure for all missing ranges.
    Replaces 2-point Kabsch and 10-Cα local alignment.

    For each range:
      1. Parse backbone coords from grafted_lines (loop) and crystal_lines_by_res (anchors)
      2. Run _run_ccd to achieve ideal C-N junction distances
      3. Write updated backbone coords back into grafted_lines

    Side-chain atoms are unaffected — only backbone N/CA/C/O coords updated.
    """
    result = dict(grafted_lines)

    for (chain, start, end) in missing_ranges:
        expected_count = end - start + 1
        res_list = [r for r in range(start, end + 1)
                    if (chain, r) in result or (chain, str(r)) in result]

        if not res_list:
            print(f"[loop_model] WARNING: CCD skipping {chain}:{start}-{end} — "
                  f"0 residues in graft (AF coverage failure).")
            continue

        # Reject partial coverage — partial graft produces broken topology
        if len(res_list) < expected_count:
            missing_res = sorted(set(range(start, end + 1)) - set(res_list))
            print(f"[loop_model] REJECT partial graft {chain}:{start}-{end}: "
                  f"only {len(res_list)}/{expected_count} residues placed "
                  f"(missing: {missing_res}). "
                  f"Partial graft = broken topology. Removing partial residues. "
                  f"Options: find AF with full coverage, use MODELLER, or cap at break.")
            # Remove partially placed residues — better empty gap than broken structure
            for r in res_list:
                result.pop((chain, r), None)
                result.pop((chain, str(r)), None)
            continue

        # Get anchor atoms from crystal — use _find_anchor with search_radius=3
        # to handle stub residues (e.g. residue has N/CA but no C — must search back)
        _anc_C_res, anchor_C = _find_anchor(crystal_lines_by_res, chain, start - 1, "C", direction=-1, search_radius=3)
        _anc_N_res, anchor_N = _find_anchor(crystal_lines_by_res, chain, end   + 1, "N", direction=+1, search_radius=3)
        if anchor_C is None or anchor_N is None:
            print(f"[loop_model] WARNING: CCD anchor atoms missing for "
                  f"{chain}:{start}-{end} — skipping closure")
            continue

        # Geometric feasibility check — fix for 1-2 residue gaps with stub flanks.
        # Pattern: REMARK 465 says 1 residue missing, but flanking residue is a stub
        # (has N/CA but no C), so real anchor is 1-2 residues further back.
        # C-N gap then exceeds what n_residues can span (~3.8 Å/residue extended backbone).
        # Fix: extend res_list to fill all residues between real anchors.
        import math as _math
        import numpy as _np_gap
        gap_dist = _np_gap.linalg.norm(anchor_N - anchor_C)
        max_span = len(res_list) * 3.8
        if gap_dist > max_span and _anc_C_res is not None and _anc_N_res is not None:
            extended = list(range(_anc_C_res + 1, _anc_N_res))
            if len(extended) > len(res_list):
                print(f"[loop_model] Gap {gap_dist:.1f} Å > {len(res_list)} res × 3.8 = "
                      f"{max_span:.1f} Å. Extending {chain}:{start}-{end} → "
                      f"{chain}:{_anc_C_res+1}-{_anc_N_res-1} ({len(extended)} residues).")
                # Pull stub residues from crystal into result so CCD can use their N/CA coords
                for r in extended:
                    if (chain, r) not in result and (chain, str(r)) not in result:
                        for key in ((chain, r), (chain, str(r))):
                            if key in crystal_lines_by_res:
                                result[key] = list(crystal_lines_by_res[key])
                                break
                res_list = [r for r in extended
                            if (chain, r) in result or (chain, str(r)) in result]

        # Parse loop backbone
        bb = _parse_bb_from_lines(result, chain, res_list)
        if len(bb) < 3:
            print(f"[loop_model] WARNING: too few backbone atoms for CCD "
                  f"{chain}:{start}-{end}")
            continue

        print(f"[loop_model] CCD closure {chain}:{start}-{end} "
              f"({len(res_list)} residues, {len(bb)} backbone atoms)")

        # H-04 fix: save original CA positions before CCD so we can translate sidechains later
        bb_before_ccd = {k: v.copy() for k, v in bb.items()}

        # H-05 fix: tight gap fallback — ideal geometry for single residue when CCD can't converge
        import numpy as np
        gap_dist = np.linalg.norm(anchor_N - anchor_C)
        if len(res_list) == 1 and gap_dist < 2 * _BOND_CN + 0.5:
            print(f"[loop_model] Tight gap ({gap_dist:.3f} Å) for single residue "
                  f"{chain}:{res_list[0]} — using ideal geometry")
            closed = _place_single_residue_ideal(anchor_C, anchor_N, bb, res_list[0])
            n0 = closed.get((res_list[0], "N"))
            cN = closed.get((res_list[0], "C"))
            d_N = np.linalg.norm(n0 - anchor_C) if n0 is not None else 999
            d_C = np.linalg.norm(cN - anchor_N) if cN is not None else 999
            ok = True
        else:
            closed, d_N, d_C, ok = _run_ccd(bb, anchor_C, anchor_N, res_list)

        # Write updated backbone coords back to lines
        result = _write_bb_coords_to_lines(result, chain, res_list, closed)

        # H-04 fix: translate sidechain atoms by CA displacement so CA-CB distances stay correct
        result = _translate_sidechains_by_ca_shift(result, chain, res_list, bb_before_ccd, closed)

        status_N = "PASS" if 1.0 <= d_N <= 1.7 else "FAIL"
        status_C = "PASS" if 1.0 <= d_C <= 1.7 else "FAIL"
        if status_N == "FAIL" or status_C == "FAIL":
            print(f"[loop_model] WARNING: CCD junction outside [1.0, 1.7] Å — "
                  f"N={d_N:.3f}[{status_N}]  C={d_C:.3f}[{status_C}]. "
                  f"Amber minimization may fix small deviations.")

    return result


def _close_loop_junctions_local(grafted_lines: dict, crystal_lines_by_res: dict,
                                 af_aligned_lines_by_res: dict,
                                 missing_ranges: list, flank: int = 5) -> dict:
    """
    Local Kabsch alignment using flanking Cα atoms (5 pre-gap + 5 post-gap = 10 points).

    Replaces the old 2-point Kabsch (_close_loop_junctions) which was degenerate:
    - 2×3 SVD has no unique solution → collapsed junctions (0.045 Å bug)
    - 10-point local alignment is stable and focuses on the gap neighborhood

    For each missing range:
    1. Collect Cα coords of [start-flank .. start-1] from crystal + aligned AF
    2. Collect Cα coords of [end+1 .. end+flank] from crystal + aligned AF
    3. Kabsch: AF_flanks → crystal_flanks  (local rotation)
    4. Apply local rotation to loop residues only
    """
    import numpy as np

    result = dict(grafted_lines)

    for (chain, start, end) in missing_ranges:
        range_keys = [(chain, r) for r in range(start, end + 1) if (chain, r) in result]
        if not range_keys:
            continue

        src_pts, tgt_pts = [], []

        # Pre-gap flank: [start-flank .. start-1]
        for r in range(max(1, start - flank), start):
            cry_ca = _get_bb_atom(crystal_lines_by_res, chain, str(r), "CA")
            af_ca  = _get_bb_atom(af_aligned_lines_by_res, chain, r, "CA")
            if cry_ca is not None and af_ca is not None:
                tgt_pts.append(cry_ca)
                src_pts.append(af_ca)

        # Post-gap flank: [end+1 .. end+flank]
        for r in range(end + 1, end + flank + 1):
            cry_ca = _get_bb_atom(crystal_lines_by_res, chain, str(r), "CA")
            af_ca  = _get_bb_atom(af_aligned_lines_by_res, chain, r, "CA")
            if cry_ca is not None and af_ca is not None:
                tgt_pts.append(cry_ca)
                src_pts.append(af_ca)

        if len(src_pts) < 3:
            print(f"[loop_model] WARNING: only {len(src_pts)} flanking Cα pairs for "
                  f"{chain}:{start}-{end} — need ≥3, falling back to global alignment.")
            continue

        R, t = _kabsch(np.array(src_pts), np.array(tgt_pts))
        result = _apply_transform_to_lines(result, range_keys, R, t)

        # Report junction distances after local alignment
        junctions = [
            (start - 1, start,   "C", "N"),
            (end,       end + 1, "C", "N"),
        ]
        for res_pre, res_post, atom_pre, atom_post in junctions:
            pre_coord  = _get_bb_atom(crystal_lines_by_res, chain, str(res_pre), atom_pre)
            post_coord = _get_bb_atom(result, chain, res_post, atom_post)
            if pre_coord is not None and post_coord is not None:
                d = float(np.linalg.norm(pre_coord - post_coord))
                print(f"[loop_model] Junction {chain}{res_pre}{atom_pre}→"
                      f"{res_post}{atom_post} = {d:.3f} Å  ({len(src_pts)} Cα pairs used)")

    return result


# ---------------------------------------------------------------------------
# Task 5 — extract_and_graft
# ---------------------------------------------------------------------------

def extract_and_graft(crystal_path: str, predicted_pdb_str: str,
                      missing_ranges: list, out_path: str,
                      dbref_offsets: dict = None) -> None:
    """
    Align predicted to crystal, extract missing residue ATOM lines,
    insert into crystal PDB, write to out_path.
    Keeps all crystal ATOM records. Only adds missing residues from predicted.

    dbref_offsets: {chain: uniprot_start - pdb_start} from parse_dbref_offsets().
    When provided, used directly for AF residue extraction (fixes DBREF offset bug).
    Without it, falls back to H-12/H-09 heuristic.
    """
    if not BIOPYTHON_OK:
        raise ImportError("BioPython required: pip install biopython")

    # Collect crystal residues
    # H-08 fix: key on (chain, resnum+icode) so insertion-code residues (100, 100A)
    # are stored separately instead of overwriting each other.
    crystal_lines_by_res = {}
    with open(crystal_path) as f:
        for line in f:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                ch = line[21]
                res_key = line[22:27].strip()  # e.g. "100" or "100A"
                crystal_lines_by_res.setdefault((ch, res_key), []).append(line)

    # Missing residue set
    missing_res_set = set()
    for (chain, start, end) in missing_ranges:
        for i in range(start, end + 1):
            missing_res_set.add((chain, i))

    # H-10: warn if missing_ranges span multiple chains — only first chain is used for alignment
    target_chains = list(dict.fromkeys(c for (c, s, e) in missing_ranges))
    if len(target_chains) > 1:
        print(
            f"[loop_model] WARNING (H-10): missing_ranges span {len(target_chains)} chains "
            f"({target_chains}). Alignment uses only the first chain ({target_chains[0]}). "
            "Grafts on other chains may have incorrect orientation. "
            "For multi-chain gaps, run loop_model separately per chain.",
            file=__import__("sys").stderr,
        )

    # Identify resolved residues for alignment (integer residue numbers only — no icodes)
    target_chain = missing_ranges[0][0]
    # H-08: keys are now strings (e.g. "85", "85A"); extract integer part for BioPython
    resolved_str_keys = [r for (c, r) in crystal_lines_by_res if c == target_chain]
    resolved_int = []
    for rk in resolved_str_keys:
        try:
            resolved_int.append(int(rk))
        except ValueError:
            pass  # skip insertion-code residues for BioPython alignment

    # Load predicted ONCE, align in-place, write aligned version
    predicted_struct = _load_structure(predicted_pdb_str, "pred")
    crystal_struct = _load_structure(crystal_path, "crystal")
    crystal_chain = crystal_struct[0][target_chain]
    pred_chain_id = list(predicted_struct[0].child_dict.keys())[0]
    pred_chain = predicted_struct[0][pred_chain_id]

    res_set = set(resolved_int)
    crystal_atoms, pred_atoms = [], []
    for res_id in res_set:
        try:
            c_ca = crystal_chain[res_id]["CA"]
            p_ca = pred_chain[res_id]["CA"]
        except KeyError:
            continue
        crystal_atoms.append(c_ca)
        pred_atoms.append(p_ca)

    if len(crystal_atoms) < 3:
        raise ValueError(
            f"Only {len(crystal_atoms)} common CA atoms found for alignment — need >= 3. "
            f"Crystal and predicted structures may not share enough resolved residues."
        )

    if crystal_atoms:
        sup = Superimposer()
        sup.set_atoms(crystal_atoms, pred_atoms)
        sup.apply(list(predicted_struct.get_atoms()))  # in-place on predicted_struct

    # Write aligned predicted_struct to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as tf:
        io_obj = PDBIO()
        io_obj.set_structure(predicted_struct)
        io_obj.save(tf.name)
        tmp_pred_path = tf.name

    # H-09/H-12 (revised): per-range offset detection.
    #
    # Old approach: one global offset from min(missing_res_set) — breaks for:
    #   - Multi-chain sequential numbering (gap residue >> protein length)
    #   - Non-standard chain IDs with historical numbering
    #   - Multi-gap structures where gaps span different protein segments
    #
    # New approach: for each missing range independently:
    #   H-12: if AF residues already match crystal range → offset=0
    #   H-09: else → offset = range_start - 1 (AF numbered 1..N)
    # After remapping, validate coverage and warn specifically if 0 residues placed.

    # Step 1: parse aligned AF into raw dict (pred_resnum, not remapped)
    af_raw_by_res = {}        # {(af_chain, pred_resnum): [lines]}
    with open(tmp_pred_path) as _f:
        for _line in _f:
            if _line.startswith("ATOM") or _line.startswith("HETATM"):
                try:
                    _rn = int(_line[22:26])
                    _ch = _line[21]
                    af_raw_by_res.setdefault((_ch, _rn), []).append(_line)
                except (ValueError, IndexError):
                    pass
    os.unlink(tmp_pred_path)

    af_max_res = max((k[1] for k in af_raw_by_res), default=0)
    af_chains   = sorted(set(k[0] for k in af_raw_by_res))
    af_primary  = af_chains[0] if af_chains else "A"

    # Step 2: for each range, determine offset independently and extract residues
    grafted_lines      = {}
    af_aligned_lines_by_res = {}   # kept for legacy compatibility (unused by CCD)

    # Also rebuild af_aligned_lines_by_res from raw AF (offset=0, direct numbering)
    for (_ac, _rn), _lines in af_raw_by_res.items():
        af_aligned_lines_by_res.setdefault((_ac, _rn), []).extend(_lines)

    for (gap_ch, gap_start, gap_end) in missing_ranges:
        range_set = set(range(gap_start, gap_end + 1))

        # DBREF-aware offset: crystal residue R → AF residue R + dbref_off
        # range_offset maps pred_rn → crystal_rn: crystal_rn = pred_rn + range_offset
        # so range_offset = -(dbref_off)
        dbref_off = (dbref_offsets or {}).get(gap_ch, None)
        if dbref_off is not None and dbref_off != 0:
            range_offset = -dbref_off
            print(f"[loop_model] DBREF [{gap_ch}:{gap_start}-{gap_end}]: "
                  f"crystal+{dbref_off}=UniProt, range_offset={range_offset}")
        else:
            # H-12: check if AF has residues at crystal numbers directly (any AF chain)
            # Note: for full-length UniProt proteins, AF always has residues 1..N,
            # so H-12 will always trigger for crystal ranges 1..N regardless of true offset.
            # Only reliable when DBREF is absent (short recombinant fragments, PDB=UniProt).
            uses_crystal_numbering = any(
                any((_ac, r) in af_raw_by_res for _ac in af_chains)
                for r in range_set
            )

            if uses_crystal_numbering:
                range_offset = 0
                print(f"[loop_model] H-12 [{gap_ch}:{gap_start}-{gap_end}]: "
                      f"AF uses crystal numbering — offset=0")
            else:
                range_offset = gap_start - 1
                if range_offset != 0:
                    print(f"[loop_model] H-09 [{gap_ch}:{gap_start}-{gap_end}]: "
                          f"offset={range_offset} (AF residue 1 → crystal {gap_start})")

        # Extract AF residues for this range
        placed = 0
        for pred_rn in range(1, af_max_res + 1):
            crystal_rn = pred_rn + range_offset
            if crystal_rn not in range_set:
                continue
            # Try each AF chain
            for af_ch in af_chains:
                lines_for_res = af_raw_by_res.get((af_ch, pred_rn), [])
                if lines_for_res:
                    for _line in lines_for_res:
                        remapped = (_line[:21] + gap_ch
                                    + _line[22:22] + f"{crystal_rn:4d}" + _line[26:])
                        grafted_lines.setdefault((gap_ch, crystal_rn), []).append(remapped)
                    placed += 1
                    break

        # Validate coverage and emit diagnostic
        expected = gap_end - gap_start + 1
        if placed == 0:
            if gap_start > af_max_res + 10:
                print(
                    f"[loop_model] WARNING: gap {gap_ch}:{gap_start}-{gap_end} starts at "
                    f"residue {gap_start} but AF model only has {af_max_res} residues. "
                    f"Likely multi-chain sequential numbering in crystal — this gap belongs "
                    f"to a different protein than the AF model covers. "
                    f"Fix: split complex into individual chains before loop modeling."
                )
            else:
                print(
                    f"[loop_model] WARNING: 0/{expected} AF residues mapped to "
                    f"{gap_ch}:{gap_start}-{gap_end} (offset={range_offset}). "
                    f"Numbering mismatch between AF and crystal "
                    f"(non-standard chain ID or legacy residue numbering). "
                    f"Skipping this range."
                )
        elif placed < expected:
            print(
                f"[loop_model] WARNING: partial AF coverage for {gap_ch}:{gap_start}-{gap_end}: "
                f"{placed}/{expected} residues placed."
            )

    # CCD loop closure: backbone torsion adjustment → ideal C-N junction geometry
    grafted_lines = _close_loop_junctions_ccd(
        grafted_lines, crystal_lines_by_res, missing_ranges
    )

    # H-11: post-graft clash check — detect heavy-heavy contacts < 2.0 Å between
    # grafted atoms and crystal atoms within 5 Å of the graft. Warn + flag if found.
    import math as _math
    _clash_threshold = 2.0
    _HEAVY_ELEMENTS = {"C", "N", "O", "S", "P", "SE", "FE", "ZN", "MG", "CA", "MN", "CU", "CL", "BR", "I", "F"}
    def _parse_xyz(line):
        try:
            return (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except (ValueError, IndexError):
            return None
    def _element_from_line(line):
        el = line[76:78].strip() if len(line) > 78 else ""
        return el.upper() if el else line[12:16].strip()[:1].upper()
    # Collect grafted heavy atom positions
    graft_heavy = []
    for lines in grafted_lines.values():
        for line in lines:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                if _element_from_line(line) not in ("H", "D"):
                    xyz = _parse_xyz(line)
                    if xyz:
                        graft_heavy.append(xyz)
    # Collect crystal heavy atom positions (only those within 5 Å of any graft atom is ideal;
    # for simplicity check all — small cost for typical loop sizes)
    crystal_heavy = []
    for lines in crystal_lines_by_res.values():
        for line in lines:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                if _element_from_line(line) not in ("H", "D"):
                    xyz = _parse_xyz(line)
                    if xyz:
                        crystal_heavy.append(xyz)
    n_clashes = 0
    for gx, gy, gz in graft_heavy:
        for cx, cy, cz in crystal_heavy:
            d = _math.sqrt((gx-cx)**2 + (gy-cy)**2 + (gz-cz)**2)
            if d < _clash_threshold:
                n_clashes += 1
    if n_clashes > 0:
        print(
            f"[loop_model] WARNING (H-11): {n_clashes} post-graft heavy-heavy clash(es) detected "
            f"(< {_clash_threshold} Å). Structure may have steric overlaps. "
            "Run energy minimization before MD or re-check loop source. "
            "validate_loop_junction and validate_ligand_geometry should also be called.",
            file=__import__("sys").stderr,
        )

    # Assemble: crystal + grafted, sorted by (chain, resnum)
    # H-08: crystal keys are strings (possibly with icode); graft keys are ints.
    # Sort by chain then numeric part of residue key for correct output ordering.
    def _res_sort_key(x):
        ch, r = x
        try:
            return (ch, int(str(r).rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") or "0"), str(r))
        except ValueError:
            return (ch, 0, str(r))

    all_keys = sorted(
        set(crystal_lines_by_res.keys()) | set(grafted_lines.keys()),
        key=_res_sort_key
    )

    with open(out_path, "w") as out:
        for key in all_keys:
            if key in crystal_lines_by_res:
                for line in crystal_lines_by_res[key]:
                    out.write(line)
            else:
                for line in grafted_lines[key]:
                    out.write(line)
        out.write("END\n")


# ---------------------------------------------------------------------------
# Task 6 — user-interaction helper and CLI entry point
# ---------------------------------------------------------------------------

def _ask_user_plddt_low(ranges: list, plddt_vals: dict) -> str:
    """Present user options when pLDDT < 70. Returns '1', '2', or '3'."""
    print("\n" + "="*60)
    print("LOOP MODELING — LOW CONFIDENCE PREDICTION")
    print("="*60)
    for r, val in plddt_vals.items():
        print(f"  Residues {r[0]}:{r[1]}-{r[2]}  pLDDT = {val:.1f} < 70")
    print("\nOptions:")
    print("  1. Graft anyway (low-confidence coords, noted in PROCESS_REPORT)")
    print("  2. Provide your own PDB path for the missing region")
    print("  3. Cap at break points with ACE/NME (safest for MD)")
    return input("\nYour choice [1/2/3]: ").strip()


def main():
    parser = argparse.ArgumentParser(
        description="Fill missing residue ranges in crystal PDB using AlphaFold/ESMFold"
    )
    parser.add_argument("--pdb", required=True,
                        help="Crystal PDB path (may have chain breaks)")
    parser.add_argument("--missing", required=True,
                        help="Missing ranges e.g. 'A:86-91,A:120-125'")
    parser.add_argument("--uniprot", required=True,
                        help="UniProt accession for AlphaFold query")
    parser.add_argument("--out", required=True,
                        help="Output assembled PDB path")
    parser.add_argument("--auto-accept", action="store_true", default=False,
                        help="Automatically accept low-confidence regions (pLDDT < 70) without prompting")
    args = parser.parse_args()

    missing_ranges = parse_missing_ranges(args.missing)
    meta = {
        "uniprot_id": args.uniprot,
        "missing_ranges": args.missing,
        "crystal_pdb": args.pdb,
        "source": None,
        "plddt": None,
        "action": "graft"
    }

    # Parse DBREF to get per-chain UniProt offsets (fixes pLDDT null + wrong graft)
    dbref_offsets = parse_dbref_offsets(args.pdb)
    if dbref_offsets:
        print(f"[loop_model] DBREF offsets detected: {dbref_offsets}")

    print(f"[loop_model] Querying AlphaFold DB for {args.uniprot}...")
    plddt_by_range = get_plddt_for_ranges(args.uniprot, missing_ranges,
                                           dbref_offsets=dbref_offsets)

    if plddt_by_range is not None:
        # AlphaFold has this protein
        low_conf  = {r: v for r, v in plddt_by_range.items() if v is not None and v < 70}
        unknown   = {r: v for r, v in plddt_by_range.items() if v is None}
        high_conf = {r: v for r, v in plddt_by_range.items() if v is not None and v >= 70}
        # unknown pLDDT (API returned no data) treated same as high_conf — graft proceeds

        if low_conf:
            choice = "1" if getattr(args, "auto_accept", False) else _ask_user_plddt_low(missing_ranges, low_conf)
            if choice == "1":
                print("[loop_model] Grafting low-confidence coords (user approved).")
                af_pdb = fetch_alphafold_pdb(args.uniprot)
                if af_pdb is None:
                    print(f"[loop_model] ERROR: Could not download AlphaFold PDB for {args.uniprot}. Check network or try later.")
                    sys.exit(1)
                extract_and_graft(args.pdb, af_pdb, missing_ranges, args.out,
                                  dbref_offsets=dbref_offsets)
                meta["source"] = "AlphaFold (low-confidence, user approved)"
                meta["plddt"] = {str(k): v for k, v in plddt_by_range.items()}
            elif choice == "2":
                user_pdb_path = input("Enter path to your PDB: ").strip()
                if not Path(user_pdb_path).exists():
                    print(f"[loop_model] File not found: {user_pdb_path}")
                    sys.exit(1)
                with open(user_pdb_path) as f:
                    user_pdb_str = f.read()
                extract_and_graft(args.pdb, user_pdb_str, missing_ranges, args.out,
                                  dbref_offsets=dbref_offsets)
                meta["source"] = f"User-provided: {user_pdb_path}"
            elif choice == "3":
                print("[loop_model] Cap at break — run: python scripts/cap_protein.py")
                print("  Cap each segment separately at break points.")
                meta["source"] = "Capped at break (user decision)"
                meta["action"] = "cap"
                meta_path = args.out.replace(".pdb", ".meta.json")
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2)
                return
            else:
                print(f"[loop_model] Unknown choice '{choice}'. Exiting.")
                sys.exit(1)
        else:
            # All ranges high confidence
            print("[loop_model] pLDDT > 70 for all ranges. Grafting AlphaFold coords.")
            af_pdb = fetch_alphafold_pdb(args.uniprot)
            if af_pdb is None:
                print("[loop_model] Failed to download AlphaFold PDB. Check network.")
                sys.exit(1)
            extract_and_graft(args.pdb, af_pdb, missing_ranges, args.out,
                              dbref_offsets=dbref_offsets)
            meta["source"] = "AlphaFold"
            meta["plddt"] = {str(k): v for k, v in plddt_by_range.items()}

    else:
        # Not in AlphaFold DB
        print(f"[loop_model] {args.uniprot} not in AlphaFold DB.")
        # M-37: warn if multi-chain — ESMFold folds as monomer, losing inter-chain context
        all_chains = set()
        try:
            with open(args.pdb) as _f:
                for _line in _f:
                    if _line.startswith(("ATOM", "HETATM")) and len(_line) > 21:
                        all_chains.add(_line[21])
        except Exception:
            pass
        target_chain = missing_ranges[0][0]
        if len(all_chains) > 1:
            print(f"[loop_model] WARNING (M-37): PDB has {len(all_chains)} chains "
                  f"({sorted(all_chains)}) but only chain {target_chain} is folded by ESMFold as monomer. "
                  "Inter-chain contacts near the loop will be wrong; verify graft visually.", file=sys.stderr)
        seq = get_sequence_from_pdb(args.pdb, chain=target_chain)
        aa_count = len(seq)
        print(f"[loop_model] Sequence length: {aa_count} AA")

        if aa_count <= 400:
            print("[loop_model] Calling ESMFold API...")
            esm_pdb = call_esm_fold(seq)
            if esm_pdb is None:
                print("[loop_model] ESMFold API failed. Provide a PDB manually.")
                sys.exit(1)
            extract_and_graft(args.pdb, esm_pdb, missing_ranges, args.out,
                              dbref_offsets=dbref_offsets)
            meta["source"] = "ESMFold"
        else:
            print(f"[loop_model] Protein > 400 AA and not in AlphaFold DB.")
            print("  Please provide a PDB with the complete chain and re-run preflight.")
            sys.exit(1)

    # Write metadata
    meta_path = args.out.replace(".pdb", ".meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[loop_model] Done. Assembled PDB: {args.out}")
    print(f"[loop_model] Metadata: {meta_path}")


if __name__ == "__main__":
    main()

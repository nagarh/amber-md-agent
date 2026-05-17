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

from alphafold_server import get_plddt_scores as alphafold_get_plddt_scores
from alphafold_server import get_prediction as alphafold_get_prediction


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


def get_plddt_for_ranges(uniprot_id: str, ranges: list) -> dict:
    """
    Query AlphaFold DB pLDDT for missing residue ranges.
    Returns None if protein not in AlphaFold DB.
    Returns {(chain, start, end): mean_plddt} otherwise.
    """
    scores = alphafold_get_plddt_scores(uniprot_id)
    if "error" in scores:
        return None  # not in DB

    residue_map = {r["residue_number"]: r["plddt"]
                   for r in scores.get("residue_scores", [])}

    result = {}
    for (chain, start, end) in ranges:
        expected = end - start + 1
        values = [residue_map[i] for i in range(start, end + 1) if i in residue_map]
        missing_count = expected - len(values)
        if missing_count > 0:
            print(f"[loop_model] WARNING: {missing_count}/{expected} residues missing from AlphaFold pLDDT for {chain}:{start}-{end}. Using conservative (lower) mean.")
            # pad with 0.0 for missing residues — conservative estimate
            mean_plddt = sum(values) / expected if expected > 0 else 0.0
        else:
            mean_plddt = sum(values) / len(values) if values else 0.0
        result[(chain, start, end)] = mean_plddt
    return result


def fetch_alphafold_pdb(uniprot_id: str) -> str:
    """Download AlphaFold PDB string. Returns None if not in DB after 3 attempts."""
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
                return resp.read().decode()
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
    """Extract one-letter sequence from CA atoms of specified chain."""
    seen = {}
    with open(pdb_path) as f:
        for line in f:
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                ch = line[21]
                if ch != chain:
                    continue
                resnum = int(line[22:26])
                resname = line[17:20].strip()
                if resnum not in seen:
                    seen[resnum] = THREE_TO_ONE.get(resname, "X")
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
    """Load BioPython structure from file path or PDB string."""
    parser = PDBParser(QUIET=True)
    if pdb_path_or_str.strip().startswith(("ATOM", "REMARK", "HEADER", "MODEL", "TITLE", "COMPND")):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
            f.write(pdb_path_or_str)
            tmp_path = f.name
        struct = parser.get_structure(struct_id, tmp_path)
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

def _get_bb_atom(lines_by_res: dict, chain: str, resnum: int, atom_name: str):
    """Return (x,y,z) of backbone atom from lines_by_res dict, or None."""
    import numpy as np
    for line in lines_by_res.get((chain, resnum), []):
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
    updated = dict(lines_dict)
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


def _close_loop_junctions(grafted_lines: dict, crystal_lines_by_res: dict,
                           missing_ranges: list) -> dict:
    """
    For each missing range independently, apply a 2-point Kabsch rigid-body
    transform so the graft's terminal N and C backbone atoms land on the
    corresponding crystal anchor atoms (C before gap, N after gap).

    Handles:
    - Multiple separate missing ranges (independent transform per range)
    - Partially-resolved residues at gap edges (searches ±3 residues for anchor)

    Falls back per-range if anchors still not found after search.
    """
    import numpy as np

    result = dict(grafted_lines)

    for (chain, start, end) in missing_ranges:
        # Collect keys for just this range
        range_keys = [(chain, r) for r in range(start, end + 1) if (chain, r) in result]
        if not range_keys:
            continue

        first_graft = start
        last_graft  = end

        # Find crystal anchors with fallback search
        n_anc_res, n_anchor_C = _find_anchor(crystal_lines_by_res, chain, first_graft - 1, "C", direction=-1)
        c_anc_res, c_anchor_N = _find_anchor(crystal_lines_by_res, chain, last_graft  + 1, "N", direction=+1)

        graft_N = _get_bb_atom(result, chain, first_graft, "N")
        graft_C = _get_bb_atom(result, chain, last_graft,  "C")

        if any(v is None for v in (n_anchor_C, c_anchor_N, graft_N, graft_C)):
            missing = [name for name, val in [
                (f"crystal {chain}{first_graft-1}C", n_anchor_C),
                (f"crystal {chain}{last_graft+1}N",  c_anchor_N),
                (f"graft {chain}{first_graft}N",      graft_N),
                (f"graft {chain}{last_graft}C",        graft_C),
            ] if val is None]
            print(f"[loop_model] WARNING: range {chain}:{start}-{end}: cannot find {missing} — skipping Procrustes for this range")
            continue

        # Pre-check: warn if AF2 loop span ≠ crystal gap width — Kabsch residual = |diff|/2
        graft_span   = float(np.linalg.norm(graft_C - graft_N))
        crystal_gap  = float(np.linalg.norm(c_anchor_N - n_anchor_C))
        span_mismatch = abs(graft_span - crystal_gap)
        expected_residual = span_mismatch / 2.0
        if expected_residual > 2.0:
            print(f"[loop_model] WARNING: range {chain}:{start}-{end}: "
                  f"AF2 loop span={graft_span:.1f} Å vs crystal gap={crystal_gap:.1f} Å "
                  f"(mismatch={span_mismatch:.1f} Å, expected residual≥{expected_residual:.1f} Å). "
                  f"AF2 conformation incompatible with this gap — consider ESMFold or a different source.")

        src = np.array([graft_N, graft_C])
        tgt = np.array([n_anchor_C, c_anchor_N])
        R, t = _kabsch(src, tgt)

        result = _apply_transform_to_lines(result, range_keys, R, t)

        # Report post-transform distances
        new_N = _get_bb_atom(result, chain, first_graft, "N")
        new_C = _get_bb_atom(result, chain, last_graft,  "C")
        if new_N is not None and new_C is not None:
            d_N = float(np.linalg.norm(new_N - n_anchor_C))
            d_C = float(np.linalg.norm(new_C - c_anchor_N))
            print(f"[loop_model] Junction closure {chain}:{start}-{end}: "
                  f"{n_anc_res}C→{first_graft}N = {d_N:.2f} Å  |  "
                  f"{last_graft}C→{c_anc_res}N = {d_C:.2f} Å")

    return result


# ---------------------------------------------------------------------------
# Task 5 — extract_and_graft
# ---------------------------------------------------------------------------

def extract_and_graft(crystal_path: str, predicted_pdb_str: str,
                      missing_ranges: list, out_path: str) -> None:
    """
    Align predicted to crystal, extract missing residue ATOM lines,
    insert into crystal PDB, write to out_path.
    Keeps all crystal ATOM records. Only adds missing residues from predicted.
    """
    if not BIOPYTHON_OK:
        raise ImportError("BioPython required: pip install biopython")

    # Collect crystal residues
    crystal_lines_by_res = {}
    with open(crystal_path) as f:
        for line in f:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                resnum = int(line[22:26])
                ch = line[21]
                crystal_lines_by_res.setdefault((ch, resnum), []).append(line)

    # Missing residue set
    missing_res_set = set()
    for (chain, start, end) in missing_ranges:
        for i in range(start, end + 1):
            missing_res_set.add((chain, i))

    # Identify resolved residues for alignment
    target_chain = missing_ranges[0][0]
    resolved = [r for (c, r) in crystal_lines_by_res if c == target_chain]

    # Load predicted ONCE, align in-place, write aligned version
    predicted_struct = _load_structure(predicted_pdb_str, "pred")
    crystal_struct = _load_structure(crystal_path, "crystal")
    crystal_chain = crystal_struct[0][target_chain]
    pred_chain_id = list(predicted_struct[0].child_dict.keys())[0]
    pred_chain = predicted_struct[0][pred_chain_id]

    res_set = set(resolved)
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

    grafted_lines = {}
    with open(tmp_pred_path) as f:
        for line in f:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                try:
                    resnum = int(line[22:26])
                    ch = line[21]
                    if (ch, resnum) in missing_res_set:
                        grafted_lines.setdefault((ch, resnum), []).append(line)
                except (ValueError, IndexError):
                    continue
    os.unlink(tmp_pred_path)

    # Close junctions: 2-point Procrustes aligns graft endpoints onto crystal anchors
    grafted_lines = _close_loop_junctions(grafted_lines, crystal_lines_by_res, missing_ranges)

    # Assemble: crystal + grafted, sorted by (chain, resnum)
    all_keys = sorted(
        set(crystal_lines_by_res.keys()) | set(grafted_lines.keys()),
        key=lambda x: (x[0], x[1])
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

    print(f"[loop_model] Querying AlphaFold DB for {args.uniprot}...")
    plddt_by_range = get_plddt_for_ranges(args.uniprot, missing_ranges)

    if plddt_by_range is not None:
        # AlphaFold has this protein
        low_conf = {r: v for r, v in plddt_by_range.items() if v < 70}
        high_conf = {r: v for r, v in plddt_by_range.items() if v >= 70}

        if low_conf:
            choice = _ask_user_plddt_low(missing_ranges, low_conf)
            if choice == "1":
                print("[loop_model] Grafting low-confidence coords (user approved).")
                af_pdb = fetch_alphafold_pdb(args.uniprot)
                if af_pdb is None:
                    print(f"[loop_model] ERROR: Could not download AlphaFold PDB for {args.uniprot}. Check network or try later.")
                    sys.exit(1)
                extract_and_graft(args.pdb, af_pdb, missing_ranges, args.out)
                meta["source"] = "AlphaFold (low-confidence, user approved)"
                meta["plddt"] = {str(k): v for k, v in plddt_by_range.items()}
            elif choice == "2":
                user_pdb_path = input("Enter path to your PDB: ").strip()
                if not Path(user_pdb_path).exists():
                    print(f"[loop_model] File not found: {user_pdb_path}")
                    sys.exit(1)
                with open(user_pdb_path) as f:
                    user_pdb_str = f.read()
                extract_and_graft(args.pdb, user_pdb_str, missing_ranges, args.out)
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
            extract_and_graft(args.pdb, af_pdb, missing_ranges, args.out)
            meta["source"] = "AlphaFold"
            meta["plddt"] = {str(k): v for k, v in plddt_by_range.items()}

    else:
        # Not in AlphaFold DB
        print(f"[loop_model] {args.uniprot} not in AlphaFold DB.")
        seq = get_sequence_from_pdb(args.pdb, chain=missing_ranges[0][0])
        aa_count = len(seq)
        print(f"[loop_model] Sequence length: {aa_count} AA")

        if aa_count <= 400:
            print("[loop_model] Calling ESMFold API...")
            esm_pdb = call_esm_fold(seq)
            if esm_pdb is None:
                print("[loop_model] ESMFold API failed. Provide a PDB manually.")
                sys.exit(1)
            extract_and_graft(args.pdb, esm_pdb, missing_ranges, args.out)
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

#!/usr/bin/env python3
"""
AlphaFold Database MCP Server for AmberMD Agent.

Access to AlphaFold predicted structures: metadata + MD suitability, structure
download (pLDDT in B-factor column), per-residue pLDDT scores, and PAE summary.

When to use AlphaFold vs PDB: no experimental structure exists; experimental has
missing loops; need a mutant/variant; need a full-length protein (PDB often
has only fragments).

Run: python alphafold_server.py [--test]
"""
import json, os, re, sys, statistics
from functools import lru_cache
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP
from _common import http_get, http_get_text, error_response, get_logger

mcp = FastMCP("alphafold-server")
logger = get_logger(__name__)

AFDB_API = "https://alphafold.ebi.ac.uk/api"
_UNIPROT_ID_RE = re.compile(r'^[A-Z0-9]+(-[A-Z0-9]+)*$')
_BLOCKED_DIRS = ("/etc/", "/bin/", "/usr/", "/sbin/", "/root/", "/proc/", "/sys/")


@lru_cache(maxsize=256)
def _fetch_prediction(uniprot_id: str) -> dict:
    """Fetch AlphaFold prediction metadata + pLDDT-based MD suitability assessment.
    Cached: repeated tool calls for the same accession skip the network round-trip.
    """
    # M-06: validate uniprot_id against safe whitelist before any network use.
    if not _UNIPROT_ID_RE.match(uniprot_id.upper() if uniprot_id else ""):
        return {"error": f"Invalid UniProt ID '{uniprot_id}': must match ^[A-Z0-9]+(-[A-Z0-9]+)*$"}
    result = http_get(f"{AFDB_API}/prediction/{uniprot_id}")
    if isinstance(result, list):
        if not result: return {"error": f"No AlphaFold prediction for {uniprot_id}"}
        result = result[0]
    if "error" in result: return result

    start, end = result.get("uniprotStart"), result.get("uniprotEnd")
    info = {
        "uniprot_id": uniprot_id, "gene": result.get("gene", ""),
        "organism": result.get("organismScientificName", ""),
        "uniprot_description": result.get("uniprotDescription", ""),
        "model_version": result.get("latestVersion", ""),
        # H-16 fix: guard against end < start (API anomaly -> negative length)
        "sequence_length": max(0, (end or 0) - (start or 0) + 1),
        "uniprot_start": start, "uniprot_end": end,
        "coverage_start": start, "coverage_end": end,
        "pdb_url": result.get("pdbUrl", ""), "cif_url": result.get("cifUrl", ""),
        "pae_image_url": result.get("paeImageUrl", ""), "pae_doc_url": result.get("paeDocUrl", ""),
        "global_plddt": result.get("globalMetricValue"),
    }
    p = info["global_plddt"]
    info["md_assessment"] = (
        {} if p is None else
        {"confidence": "very_high", "recommendation": "Excellent for MD. Structure is highly confident."} if p > 90 else
        {"confidence": "high", "recommendation": "Good for MD. Some flexible regions may have lower confidence - check pLDDT per residue."} if p > 70 else
        {"confidence": "medium", "recommendation": "Use with caution. Significant regions may be poorly predicted. Consider longer equilibration or restraining low-confidence regions."} if p > 50 else
        {"confidence": "low", "recommendation": "Not recommended for direct MD. Many regions are likely disordered or incorrectly predicted. Consider experimental structure instead."})
    return info


@mcp.tool()
def get_prediction(uniprot_id: str) -> dict:
    """Get AlphaFold prediction metadata: confidence, model URLs, MD suitability.
    Use when no experimental structure exists or you need full-length predicted.
    """
    return _fetch_prediction(uniprot_id)


@mcp.tool()
def download_structure(uniprot_id: str, output_path: Optional[str] = None, fmt: str = "pdb") -> dict:
    """Download AlphaFold predicted structure as PDB or CIF.
    pLDDT in B-factor column. Ready for pdb4amber + tLEaP.
    """
    pred = _fetch_prediction(uniprot_id)
    if "error" in pred: return pred
    url = pred.get("cif_url" if fmt == "cif" else "pdb_url", "")
    if not url: return {"error": f"No {fmt} URL available for {uniprot_id}"}
    content = http_get_text(url)
    if not content: return {"error": f"Failed to download structure for {uniprot_id}"}

    result = {"uniprot_id": uniprot_id, "format": fmt, "size_bytes": len(content),
              "global_plddt": pred.get("global_plddt"), "md_assessment": pred.get("md_assessment", {})}
    if output_path:
        # C-06 fix: path-traversal validation - reject '..' components and blocked system dirs.
        if ".." in Path(output_path).parts:
            return {"status": "error", "error": "output_path must not contain '..' components"}
        real_output = os.path.realpath(output_path)
        if any(real_output.startswith(p) for p in _BLOCKED_DIRS):
            return {"status": "error", "error": f"output_path resolves to a blocked system directory: {real_output}"}
        with open(output_path, 'w') as f:
            f.write(content)
        result["saved_to"] = output_path
        result["note"] = "pLDDT scores are in the B-factor column. Residues with pLDDT < 50 are unreliable."
    else:
        result["content"] = content
    return result


@mcp.tool()
def get_plddt_scores(uniprot_id: str) -> dict:
    """Per-residue pLDDT scores + low-confidence regions. Use for restraint masks.
    pLDDT: >90 very high; 70-90 confident; 50-70 low; <50 very low (likely disordered).
    """
    pred = _fetch_prediction(uniprot_id)
    if "error" in pred: return pred
    url = pred.get("pdb_url", "")
    if not url: return {"error": "No PDB available"}
    content = http_get_text(url)
    if not content: return {"error": "Failed to download"}

    # Single-pass parse of pLDDT (B-factor column) from CA atoms + contiguous low regions.
    residue_scores, low_regions, in_low, start = [], [], False, 0
    for line in content.split('\n'):
        if not (line.startswith("ATOM") and line[12:16].strip() == "CA"):
            continue
        try:  # H-17 fix: guard both numeric parses
            resnum = int(line[22:26].strip())
            bf = round(float(line[60:66].strip()), 1)  # pLDDT is in B-factor
        except (ValueError, IndexError):
            continue
        residue_scores.append({"residue": resnum, "resname": line[17:20].strip(),
                               "chain": line[21].strip() if len(line) > 21 else "", "plddt": bf})
        if bf < 50:
            if not in_low: start, in_low = resnum, True
        elif in_low:
            low_regions.append({"start": start, "end": resnum - 1}); in_low = False
    if in_low:
        low_regions.append({"start": start, "end": residue_scores[-1]["residue"]})

    scores = [r["plddt"] for r in residue_scores]
    n = len(scores)
    return {
        "uniprot_id": uniprot_id, "n_residues": n,
        "global_plddt": round(sum(scores) / n, 1) if n else None,
        "confidence_distribution": {
            "very_high_gt90": sum(1 for s in scores if s > 90),
            "high_70_90": sum(1 for s in scores if 70 < s <= 90),
            "low_50_70": sum(1 for s in scores if 50 < s <= 70),
            "very_low_lt50": sum(1 for s in scores if s <= 50)},
        "low_confidence_regions": low_regions,
        "md_restraint_suggestion": (
            "Consider restraining residues in these low-confidence regions: "
            + ", ".join(f"{r['start']}-{r['end']}" for r in low_regions)
            if low_regions else "No low-confidence regions - structure looks reliable"),
        "per_residue": residue_scores,
    }


@mcp.tool()
def get_pae(uniprot_id: str) -> dict:
    """Predicted Aligned Error summary. Tells if domain-domain arrangements are
    trustworthy. Low PAE = confident relative positioning; high PAE = uncertain.
    """
    pred = _fetch_prediction(uniprot_id)
    if "error" in pred: return pred
    pae_url = pred.get("pae_doc_url", "")
    if not pae_url: return {"error": "No PAE data available"}
    pae_data = http_get(pae_url)
    if "error" in pae_data: return pae_data

    if isinstance(pae_data, list) and pae_data:  # one entry holds the error matrix
        matrix = pae_data[0].get("predicted_aligned_error", [])
        # C-07 fix: guard against empty matrix before statistics.mean/max (raise on []).
        flat = [v for row in matrix for v in row]
        if not flat:
            return {"error": "empty_pae", "uniprot_id": uniprot_id,
                    "message": "PAE matrix is empty - no values to compute statistics on"}
        return {
            "uniprot_id": uniprot_id, "matrix_size": len(matrix),
            "mean_pae": round(statistics.mean(flat), 2),
            "median_pae": round(statistics.median(flat), 2), "max_pae": round(max(flat), 2),
            "note": ("Low PAE (<5 A) between residue pairs means confident relative positioning. "
                     "High PAE (>15 A) means the relative positions are uncertain - "
                     "be cautious about inter-domain distances in MD."),
            "pae_image_url": pred.get("pae_image_url", "")}
    return {"error": "Could not parse PAE data", "raw": str(pae_data)[:500]}


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("=== AlphaFold Prediction: P00533 (EGFR) ===")
        print(json.dumps(get_prediction("P00533"), indent=2))
    else:
        mcp.run()

        
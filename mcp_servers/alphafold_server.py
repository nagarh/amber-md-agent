#!/usr/bin/env python3
"""
AlphaFold Database MCP Server for AmberMD Agent.

Gives the agent access to AlphaFold predicted structures:
- Get predicted structure for any UniProt accession
- pLDDT confidence scores (know which regions to trust)
- PAE (Predicted Aligned Error) for domain interactions
- Download CIF/PDB files ready for MD preparation
- Compare with experimental structures

When to use AlphaFold vs PDB:
- No experimental structure exists → AlphaFold is your only option
- Experimental structure has missing loops → AlphaFold can fill gaps
- Need a mutant structure → AlphaFold for the variant
- Want to simulate a full-length protein → AlphaFold (PDB often has fragments)

Run: python alphafold_server.py
     python alphafold_server.py --test
"""

import json
import sys
import urllib.request
import urllib.parse

AFDB_API = "https://alphafold.ebi.ac.uk/api"


def _http_get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "AmberMD-Agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"error": f"Not found (404): {url}"}
        return {"error": f"HTTP {e.code}: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def _http_get_raw(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AmberMD-Agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode()
    except Exception:
        return None


# ─── Tool Implementations ───────────────────────────────────────────────────

def get_prediction(uniprot_id):
    """Get AlphaFold prediction metadata for a UniProt accession.

    Returns: model URLs, confidence summary, coverage, version info.
    The agent uses this to decide whether AlphaFold structure is suitable for MD.
    """
    result = _http_get(f"{AFDB_API}/prediction/{uniprot_id}")

    if isinstance(result, list) and len(result) > 0:
        result = result[0]
    elif isinstance(result, list):
        return {"error": f"No AlphaFold prediction for {uniprot_id}"}

    if "error" in result:
        return result

    info = {
        "uniprot_id": uniprot_id,
        "gene": result.get("gene", ""),
        "organism": result.get("organismScientificName", ""),
        "uniprot_description": result.get("uniprotDescription", ""),
        "model_version": result.get("latestVersion", ""),
        "sequence_length": result.get("uniprotEnd", 0) - result.get("uniprotStart", 0) + 1,
        "uniprot_start": result.get("uniprotStart"),
        "uniprot_end": result.get("uniprotEnd"),
        "coverage_start": result.get("uniprotStart"),
        "coverage_end": result.get("uniprotEnd"),

        # URLs for downloading
        "pdb_url": result.get("pdbUrl", ""),
        "cif_url": result.get("cifUrl", ""),
        "pae_image_url": result.get("paeImageUrl", ""),
        "pae_doc_url": result.get("paeDocUrl", ""),

        # Confidence
        "global_plddt": result.get("globalMetricValue"),
    }

    # MD suitability assessment based on pLDDT
    plddt = info.get("global_plddt")
    info["md_assessment"] = {}
    if plddt is not None:
        if plddt > 90:
            info["md_assessment"]["confidence"] = "very_high"
            info["md_assessment"]["recommendation"] = "Excellent for MD. Structure is highly confident."
        elif plddt > 70:
            info["md_assessment"]["confidence"] = "high"
            info["md_assessment"]["recommendation"] = ("Good for MD. Some flexible regions may have "
                                                        "lower confidence — check pLDDT per residue.")
        elif plddt > 50:
            info["md_assessment"]["confidence"] = "medium"
            info["md_assessment"]["recommendation"] = ("Use with caution. Significant regions may be "
                                                        "poorly predicted. Consider longer equilibration "
                                                        "or restraining low-confidence regions.")
        else:
            info["md_assessment"]["confidence"] = "low"
            info["md_assessment"]["recommendation"] = ("Not recommended for direct MD. Many regions are "
                                                        "likely disordered or incorrectly predicted. "
                                                        "Consider experimental structure instead.")

    return info


def download_structure(uniprot_id, output_path=None, format="pdb"):
    """Download AlphaFold predicted structure as PDB or CIF.

    The PDB file can be directly used with pdb4amber and tLEaP.
    pLDDT scores are stored in the B-factor column — useful for
    identifying reliable vs unreliable regions.
    """
    # Get prediction info first
    pred = get_prediction(uniprot_id)
    if "error" in pred:
        return pred

    if format == "cif":
        url = pred.get("cif_url", "")
    else:
        url = pred.get("pdb_url", "")

    if not url:
        return {"error": f"No {format} URL available for {uniprot_id}"}

    content = _http_get_raw(url)
    if not content:
        return {"error": f"Failed to download structure for {uniprot_id}"}

    result = {
        "uniprot_id": uniprot_id,
        "format": format,
        "size_bytes": len(content),
        "global_plddt": pred.get("global_plddt"),
        "md_assessment": pred.get("md_assessment", {}),
    }

    if output_path:
        with open(output_path, 'w') as f:
            f.write(content)
        result["saved_to"] = output_path
        result["note"] = "pLDDT scores are in the B-factor column. Residues with pLDDT < 50 are unreliable."
    else:
        # Return content directly (agent can write it)
        result["content"] = content

    return result


def get_plddt_scores(uniprot_id):
    """Get per-residue pLDDT confidence scores.

    Returns pLDDT for each residue. The agent uses this to:
    - Decide which regions to restrain during equilibration
    - Identify flexible/disordered regions to exclude from analysis
    - Assess whether the model is reliable for the region of interest

    pLDDT interpretation:
    - >90: Very high confidence (backbone likely accurate)
    - 70-90: Confident (good for most analyses)
    - 50-70: Low confidence (may be flexible or disordered)
    - <50: Very low (likely disordered, don't trust this region)
    """
    # Download PDB and parse B-factors (which contain pLDDT)
    pred = get_prediction(uniprot_id)
    if "error" in pred:
        return pred

    url = pred.get("pdb_url", "")
    if not url:
        return {"error": "No PDB available"}

    content = _http_get_raw(url)
    if not content:
        return {"error": "Failed to download"}

    # Parse pLDDT from B-factor column of CA atoms
    residue_scores = []
    for line in content.split('\n'):
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            resnum = int(line[22:26].strip())
            resname = line[17:20].strip()
            chain = line[21].strip()
            try:
                bfactor = float(line[60:66].strip())  # pLDDT is in B-factor
            except ValueError:
                continue
            residue_scores.append({
                "residue": resnum,
                "resname": resname,
                "chain": chain,
                "plddt": round(bfactor, 1),
            })

    # Summary statistics
    scores = [r["plddt"] for r in residue_scores]
    n = len(scores)

    # Classify regions
    very_high = sum(1 for s in scores if s > 90)
    high = sum(1 for s in scores if 70 < s <= 90)
    low = sum(1 for s in scores if 50 < s <= 70)
    very_low = sum(1 for s in scores if s <= 50)

    # Find contiguous low-confidence regions (for restraint masks)
    low_regions = []
    in_low = False
    start = 0
    for r in residue_scores:
        if r["plddt"] < 50:
            if not in_low:
                start = r["residue"]
                in_low = True
        else:
            if in_low:
                low_regions.append({"start": start, "end": r["residue"] - 1})
                in_low = False
    if in_low:
        low_regions.append({"start": start, "end": residue_scores[-1]["residue"]})

    return {
        "uniprot_id": uniprot_id,
        "n_residues": n,
        "global_plddt": round(sum(scores) / n, 1) if n > 0 else None,
        "confidence_distribution": {
            "very_high_gt90": very_high,
            "high_70_90": high,
            "low_50_70": low,
            "very_low_lt50": very_low,
        },
        "low_confidence_regions": low_regions,
        "md_restraint_suggestion": (
            f"Consider restraining residues in these low-confidence regions: "
            f"{', '.join(f'{r['start']}-{r['end']}' for r in low_regions)}"
            if low_regions else "No low-confidence regions — structure looks reliable"
        ),
        "per_residue": residue_scores,
    }


def get_pae(uniprot_id):
    """Get Predicted Aligned Error (PAE) matrix summary.

    PAE tells you how confident AlphaFold is about the RELATIVE positions
    of residue pairs. Low PAE between two domains = confident interaction.
    High PAE = those domains might not be positioned correctly relative to each other.

    Critical for multi-domain proteins where you need to know if the
    domain arrangement is trustworthy for MD.
    """
    pred = get_prediction(uniprot_id)
    if "error" in pred:
        return pred

    pae_url = pred.get("pae_doc_url", "")
    if not pae_url:
        return {"error": "No PAE data available"}

    pae_data = _http_get(pae_url)
    if "error" in pae_data:
        return pae_data

    # PAE data is a list with one entry containing the error matrix
    if isinstance(pae_data, list) and len(pae_data) > 0:
        pae_entry = pae_data[0]
        predicted_aligned_error = pae_entry.get("predicted_aligned_error", [])

        if predicted_aligned_error:
            import statistics
            # Flatten to get overall statistics
            flat = []
            for row in predicted_aligned_error:
                flat.extend(row)

            return {
                "uniprot_id": uniprot_id,
                "matrix_size": len(predicted_aligned_error),
                "mean_pae": round(statistics.mean(flat), 2),
                "median_pae": round(statistics.median(flat), 2),
                "max_pae": round(max(flat), 2),
                "note": ("Low PAE (<5 Å) between residue pairs means confident relative positioning. "
                         "High PAE (>15 Å) means the relative positions are uncertain — "
                         "be cautious about inter-domain distances in MD."),
                "pae_image_url": pred.get("pae_image_url", ""),
            }

    return {"error": "Could not parse PAE data", "raw": str(pae_data)[:500]}


# ─── MCP Protocol ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_prediction",
        "description": "Get AlphaFold prediction metadata: confidence scores, model version, download URLs, and MD suitability assessment. Use when no experimental structure exists or you need full-length predicted structure.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uniprot_id": {"type": "string", "description": "UniProt accession (e.g., P00533)"}
            },
            "required": ["uniprot_id"]
        }
    },
    {
        "name": "download_structure",
        "description": "Download AlphaFold predicted structure as PDB or CIF file. pLDDT scores are in the B-factor column. Ready for pdb4amber and tLEaP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uniprot_id": {"type": "string", "description": "UniProt accession"},
                "output_path": {"type": "string", "description": "Save file to this path (optional)"},
                "format": {"type": "string", "enum": ["pdb", "cif"], "description": "File format (default: pdb)"},
            },
            "required": ["uniprot_id"]
        }
    },
    {
        "name": "get_plddt_scores",
        "description": "Get per-residue pLDDT confidence scores. Essential for knowing which parts of the AlphaFold model to trust. Includes MD restraint suggestions for low-confidence regions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uniprot_id": {"type": "string", "description": "UniProt accession"}
            },
            "required": ["uniprot_id"]
        }
    },
    {
        "name": "get_pae",
        "description": "Get Predicted Aligned Error summary. Tells you if domain-domain arrangements are trustworthy. Critical for multi-domain protein simulations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uniprot_id": {"type": "string", "description": "UniProt accession"}
            },
            "required": ["uniprot_id"]
        }
    },
]


def handle_tool_call(name, arguments):
    if name == "get_prediction": return get_prediction(**arguments)
    elif name == "download_structure": return download_structure(**arguments)
    elif name == "get_plddt_scores": return get_plddt_scores(**arguments)
    elif name == "get_pae": return get_pae(**arguments)
    else: return {"error": f"Unknown tool: {name}"}


def run_mcp_server():
    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            request = json.loads(line.strip())
            method = request.get("method", "")
            if method == "initialize":
                response = {"jsonrpc": "2.0", "id": request.get("id"),
                            "result": {"protocolVersion": "2024-11-05",
                                       "serverInfo": {"name": "alphafold-server", "version": "1.0.0"},
                                       "capabilities": {"tools": {}}}}
            elif method == "tools/list":
                response = {"jsonrpc": "2.0", "id": request.get("id"), "result": {"tools": TOOLS}}
            elif method == "tools/call":
                params = request.get("params", {})
                result = handle_tool_call(params.get("name", ""), params.get("arguments", {}))
                response = {"jsonrpc": "2.0", "id": request.get("id"),
                            "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}}
            else:
                response = {"jsonrpc": "2.0", "id": request.get("id"), "result": {}}
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except (json.JSONDecodeError, EOFError): break
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n"); sys.stderr.flush()


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("=== AlphaFold Prediction: P00533 (EGFR) ===")
        print(json.dumps(get_prediction("P00533"), indent=2))
    else:
        run_mcp_server()

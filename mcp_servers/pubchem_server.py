#!/usr/bin/env python3
"""
PubChem MCP Server for AmberMD Agent.

Gives the agent small molecule intelligence:
- Search compounds by name or SMILES
- Get 3D conformers (SDF) for antechamber parametrization
- Properties: LogP, pKa, MW, rotatable bonds, HBA/HBD
- Bioassay data for experimental validation
- Tautomers and protonation states (critical for MD accuracy)

Run: python pubchem_server.py
     python pubchem_server.py --test
"""

import json
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP
from _common import http_get, http_get_text, error_response, get_logger

mcp = FastMCP("pubchem-server")
logger = get_logger(__name__)

PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


# ─── Tool Implementations ───────────────────────────────────────────────────

def _search_compound_impl(query: str, search_type: str = "name", max_results: int = 5) -> dict:
    """Implementation of search_compound — used by both the MCP tool and external callers."""
    encoded = urllib.parse.quote(query)

    if search_type == "smiles":
        url = f"{PUBCHEM_API}/compound/smiles/{encoded}/cids/JSON"
    elif search_type == "inchi":
        url = f"{PUBCHEM_API}/compound/inchi/{encoded}/cids/JSON"
    else:
        url = f"{PUBCHEM_API}/compound/name/{encoded}/cids/JSON"

    result = http_get(url, return_text_on_parse_fail=True)
    if "error" in result:
        return result
    # M-07 fix: raw_text key signals parse failure (e.g. HTML 503 error page)
    if "raw_text" in result:
        return {"error": "pubchem_parse_fail", "query": query, "detail": "API returned non-JSON (likely HTML error page)"}

    cids = result.get("IdentifierList", {}).get("CID", [])
    if not cids:
        return {"query": query, "results": [], "message": "No compounds found"}

    # Get properties for top results
    cid_list = ",".join(str(c) for c in cids[:max_results])
    props_url = (f"{PUBCHEM_API}/compound/cid/{cid_list}/property/"
                 f"MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,"
                 f"InChI,InChIKey,IUPACName,XLogP,TPSA,HBondDonorCount,"
                 f"HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,Charge/JSON")

    props = http_get(props_url, return_text_on_parse_fail=True)
    compounds = []

    for entry in props.get("PropertyTable", {}).get("Properties", []):
        compounds.append({
            "cid": entry.get("CID"),
            "name": entry.get("IUPACName", ""),
            "formula": entry.get("MolecularFormula", ""),
            "molecular_weight": entry.get("MolecularWeight"),
            "canonical_smiles": entry.get("CanonicalSMILES", ""),
            "isomeric_smiles": entry.get("IsomericSMILES", ""),
            "inchi": entry.get("InChI", ""),
            "inchikey": entry.get("InChIKey", ""),
            "xlogp": entry.get("XLogP"),
            "tpsa": entry.get("TPSA"),
            "hbd": entry.get("HBondDonorCount"),
            "hba": entry.get("HBondAcceptorCount"),
            "rotatable_bonds": entry.get("RotatableBondCount"),
            "heavy_atoms": entry.get("HeavyAtomCount"),
            "formal_charge": entry.get("Charge"),
        })

    return {"query": query, "results": compounds}

@mcp.tool()
def search_compound(query: str, search_type: str = "name", max_results: int = 5) -> dict:
    """Search PubChem for compounds by name, SMILES, or InChI.
    Returns CID, SMILES, MW, LogP, charge, properties for MD parametrization.

    Args:
        query: Compound name (e.g., "imatinib"), SMILES, or InChI
        search_type: "name", "smiles", or "inchi"
        max_results: Number of results
    """
    return _search_compound_impl(query, search_type, max_results)


@mcp.tool()
def get_compound_properties(cid: int) -> dict:
    """Get detailed properties of a compound by PubChem CID.
    Includes MD-specific notes (formal charge for antechamber, flexibility).

    Returns everything needed for MD parametrization:
    - SMILES (canonical and isomeric)
    - Formal charge (critical for antechamber)
    - LogP, pKa estimates, TPSA
    - 2D/3D availability
    """
    props_url = (f"{PUBCHEM_API}/compound/cid/{cid}/property/"
                 f"MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,"
                 f"InChI,InChIKey,IUPACName,XLogP,TPSA,Complexity,"
                 f"HBondDonorCount,HBondAcceptorCount,RotatableBondCount,"
                 f"HeavyAtomCount,Charge,ExactMass,MonoisotopicMass/JSON")

    result = http_get(props_url, return_text_on_parse_fail=True)
    # M-08 fix: raw_text key signals parse failure (e.g. HTML 503 error page)
    if "error" in result:
        return result
    if "raw_text" in result:
        return {"error": "pubchem_parse_fail", "cid": cid, "detail": "API returned non-JSON (likely HTML error page)"}
    props_list = result.get("PropertyTable", {}).get("Properties", [])
    if not props_list:
        return {"error": f"CID {cid} not found"}

    props = props_list[0]

    # Check 3D conformer availability
    conf_url = f"{PUBCHEM_API}/compound/cid/{cid}/record/SDF/?record_type=3d"
    has_3d = http_get_text(conf_url) is not None

    # Get synonyms (common names)
    syn_url = f"{PUBCHEM_API}/compound/cid/{cid}/synonyms/JSON"
    syn_result = http_get(syn_url, return_text_on_parse_fail=True)
    synonyms = []
    syn_info = syn_result.get("InformationList", {}).get("Information", [])
    if syn_info:
        synonyms = syn_info[0].get("Synonym", [])[:10]

    return {
        "cid": cid,
        "names": synonyms,
        "iupac_name": props.get("IUPACName", ""),
        "formula": props.get("MolecularFormula", ""),
        "molecular_weight": props.get("MolecularWeight"),
        "exact_mass": props.get("ExactMass"),
        "canonical_smiles": props.get("CanonicalSMILES", ""),
        "isomeric_smiles": props.get("IsomericSMILES", ""),
        "inchi": props.get("InChI", ""),
        "inchikey": props.get("InChIKey", ""),
        "formal_charge": props.get("Charge", 0),
        "xlogp": props.get("XLogP"),
        "tpsa": props.get("TPSA"),
        "complexity": props.get("Complexity"),
        "hbd": props.get("HBondDonorCount"),
        "hba": props.get("HBondAcceptorCount"),
        "rotatable_bonds": props.get("RotatableBondCount"),
        "heavy_atoms": props.get("HeavyAtomCount"),
        "has_3d_conformer": has_3d,
        "md_notes": {
            "charge_for_antechamber": props.get("Charge", 0),
            "smiles_for_parametrization": props.get("CanonicalSMILES", ""),
            "flexibility": "high" if (props.get("RotatableBondCount") or 0) > 10 else
                           "medium" if (props.get("RotatableBondCount") or 0) > 5 else "low",
        }
    }


@mcp.tool()
def get_3d_conformer(cid: int, output_path: Optional[str] = None) -> dict:
    """Download 3D conformer as SDF file.
    Starting geometry for antechamber. Raises if only 2D available.

    This is the starting geometry for antechamber parametrization.
    If no 3D conformer exists in PubChem, returns 2D with a warning.
    """
    # Try 3D first
    url_3d = f"{PUBCHEM_API}/compound/cid/{cid}/record/SDF/?record_type=3d"
    sdf = http_get_text(url_3d)

    if sdf and len(sdf) > 100:
        source = "3d"
    else:
        # 3D conformer is unavailable — do NOT fall back to 2D silently.
        # 2D coordinates break RDKit AddHs and antechamber parametrization.
        raise RuntimeError(
            f"No 3D conformer available for CID {cid}. "
            f"2D coordinates cannot be used for MD parametrization. "
            f"Options: (1) Generate 3D coords with RDKit ETKDG from SMILES, "
            f"(2) Use a crystal structure HETATM from the PDB, "
            f"(3) Provide a mol2/SDF file with 3D coordinates."
        )

    # M-10 fix: removed dead branch (unreachable due to raise at line above)
    result = {
        "cid": cid,
        "source": source,
        "is_3d": True,
        "sdf_length": len(sdf),
        "sdf_content": sdf,
    }

    if output_path:
        # C-03 fix: path traversal validation — reject '..' components (traversal attack vector)
        # and absolute paths pointing to sensitive system directories.
        _BLOCKED_PREFIXES = ("/etc/", "/bin/", "/usr/", "/sbin/", "/root/", "/proc/", "/sys/")
        if ".." in Path(output_path).parts:
            return {"status": "error", "error": "output_path must not contain '..' components"}
        real_output = os.path.realpath(output_path)
        if any(real_output.startswith(p) for p in _BLOCKED_PREFIXES):
            return {"status": "error", "error": f"output_path resolves to a blocked system directory: {real_output}"}
        with open(output_path, 'w') as f:
            f.write(sdf)
        result["saved_to"] = output_path

    return result


@mcp.tool()
def get_bioassay_summary(cid: int, target_name: Optional[str] = None) -> dict:
    """Get bioassay activity (IC50, Ki, EC50) for a compound.
    Use to validate MD-computed binding free energies vs experiment.

    Returns activity data (IC50, EC50, Ki, etc.) that can be used
    to validate MD-computed binding free energies.
    """
    url = f"{PUBCHEM_API}/compound/cid/{cid}/assaysummary/JSON"
    result = http_get(url, return_text_on_parse_fail=True)

    if "error" in result:
        return result
    # M-11 fix: raw_text key signals parse failure (e.g. HTML 503 error page)
    if "raw_text" in result:
        return {"error": "pubchem_parse_fail", "cid": cid, "detail": "bioassay API returned non-JSON (likely HTML error page)"}

    table = result.get("Table", {})
    columns = table.get("Columns", {}).get("Column", [])
    rows = table.get("Row", [])

    activities = []
    for row in rows[:50]:  # Limit to 50 results
        cells = row.get("Cell", [])
        if len(cells) < len(columns):
            continue

        entry = {}
        for col, val in zip(columns, cells):
            entry[col] = val

        # Filter by target if specified
        if target_name:
            target_col = entry.get("Target Name", entry.get("Target GeneSymbol", ""))
            if target_name.lower() not in target_col.lower():
                continue

        # Only include active results with quantitative data
        outcome = entry.get("Activity Outcome", "")
        if outcome == "Active" or entry.get("Activity Value"):
            activities.append({
                "aid": entry.get("AID", ""),
                "target": entry.get("Target Name", ""),
                "gene": entry.get("Target GeneSymbol", ""),
                "outcome": outcome,
                "activity_value": entry.get("Activity Value"),
                "activity_name": entry.get("Activity Name", ""),
            })

    return {
        "cid": cid,
        "target_filter": target_name,
        "n_activities": len(activities),
        "activities": activities[:20],  # Top 20
    }


@mcp.tool()
def get_similar_compounds(cid: int, threshold: int = 90, max_results: int = 10) -> dict:
    """Find structurally similar compounds (Tanimoto 2D).
    Useful for congeneric series FEP, analog identification.

    Useful for:
    - Finding analogs for congeneric series FEP
    - Identifying related compounds with different activity
    - Building compound libraries for virtual screening validation
    """
    # L-04: clamp threshold to PubChem-accepted range [0, 100]
    if not 0 <= threshold <= 100:
        return {"error": "invalid_threshold", "detail": f"threshold must be 0-100, got {threshold}", "cid": cid}
    # L-05: clamp max_results to prevent oversized URLs
    if max_results < 1 or max_results > 1000:
        return {"error": "invalid_max_results", "detail": f"max_results must be 1-1000, got {max_results}", "cid": cid}
    url = (f"{PUBCHEM_API}/compound/fastsimilarity_2d/cid/{cid}/cids/JSON"
           f"?Threshold={threshold}&MaxRecords={max_results}")
    result = http_get(url, return_text_on_parse_fail=True)

    if "error" in result:
        return result

    cids = result.get("IdentifierList", {}).get("CID", [])
    if not cids:
        return {"cid": cid, "similar": []}

    # Get basic properties
    cid_list = ",".join(str(c) for c in cids[:max_results])
    props_url = (f"{PUBCHEM_API}/compound/cid/{cid_list}/property/"
                 f"MolecularFormula,MolecularWeight,CanonicalSMILES,IUPACName/JSON")
    props = http_get(props_url, return_text_on_parse_fail=True)
    # M-09 fix: check error/raw_text before accessing PropertyTable
    if "error" in props:
        return {"query_cid": cid, "threshold": threshold, "similar": [], "warning": str(props.get("error"))}
    if "raw_text" in props:
        return {"query_cid": cid, "threshold": threshold, "similar": [], "warning": "properties API returned non-JSON"}

    similar = []
    for p in props.get("PropertyTable", {}).get("Properties", []):
        similar.append({
            "cid": p.get("CID"),
            "name": p.get("IUPACName", ""),
            "formula": p.get("MolecularFormula", ""),
            "mw": p.get("MolecularWeight"),
            "smiles": p.get("CanonicalSMILES", ""),
        })

    return {"query_cid": cid, "threshold": threshold, "similar": similar}


if __name__ == "__main__":
    if "--test" in sys.argv:
        logger.debug("=== Search: erlotinib ===")
        logger.debug(json.dumps(search_compound("erlotinib", max_results=2), indent=2))
        logger.debug("\n=== Properties: CID 176870 (erlotinib) ===")
        logger.debug(json.dumps(get_compound_properties(176870), indent=2))
    else:
        mcp.run()

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
import sys
import urllib.request
import urllib.parse

PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


def _http_get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "AmberMD-Agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode()
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {"raw_text": data}
    except Exception as e:
        return {"error": str(e)}


def _http_get_raw(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AmberMD-Agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode()
    except Exception as e:
        return None


# ─── Tool Implementations ───────────────────────────────────────────────────

def search_compound(query, search_type="name", max_results=5):
    """Search PubChem for compounds by name, SMILES, or InChI.

    Args:
        query: Compound name (e.g., "imatinib"), SMILES, or InChI
        search_type: "name", "smiles", or "inchi"
        max_results: Number of results
    """
    encoded = urllib.parse.quote(query)

    if search_type == "smiles":
        url = f"{PUBCHEM_API}/compound/smiles/{encoded}/cids/JSON"
    elif search_type == "inchi":
        url = f"{PUBCHEM_API}/compound/inchi/{encoded}/cids/JSON"
    else:
        url = f"{PUBCHEM_API}/compound/name/{encoded}/cids/JSON"

    result = _http_get(url)
    if "error" in result:
        return result

    cids = result.get("IdentifierList", {}).get("CID", [])
    if not cids:
        return {"query": query, "results": [], "message": "No compounds found"}

    # Get properties for top results
    cid_list = ",".join(str(c) for c in cids[:max_results])
    props_url = (f"{PUBCHEM_API}/compound/cid/{cid_list}/property/"
                 f"MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,"
                 f"InChI,InChIKey,IUPACName,XLogP,TPSA,HBondDonorCount,"
                 f"HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,Charge/JSON")

    props = _http_get(props_url)
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


def get_compound_properties(cid):
    """Get detailed properties of a compound by PubChem CID.

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

    result = _http_get(props_url)
    props_list = result.get("PropertyTable", {}).get("Properties", [])
    if not props_list:
        return {"error": f"CID {cid} not found"}

    props = props_list[0]

    # Check 3D conformer availability
    conf_url = f"{PUBCHEM_API}/compound/cid/{cid}/record/SDF/?record_type=3d"
    has_3d = _http_get_raw(conf_url) is not None

    # Get synonyms (common names)
    syn_url = f"{PUBCHEM_API}/compound/cid/{cid}/synonyms/JSON"
    syn_result = _http_get(syn_url)
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


def get_3d_conformer(cid, output_path=None):
    """Download 3D conformer as SDF file.

    This is the starting geometry for antechamber parametrization.
    If no 3D conformer exists in PubChem, returns 2D with a warning.
    """
    # Try 3D first
    url_3d = f"{PUBCHEM_API}/compound/cid/{cid}/record/SDF/?record_type=3d"
    sdf = _http_get_raw(url_3d)

    if sdf and len(sdf) > 100:
        source = "3d"
    else:
        # Fall back to 2D
        url_2d = f"{PUBCHEM_API}/compound/cid/{cid}/record/SDF/?record_type=2d"
        sdf = _http_get_raw(url_2d)
        source = "2d"

    if not sdf or len(sdf) < 100:
        return {"error": f"No conformer available for CID {cid}"}

    result = {
        "cid": cid,
        "source": source,
        "sdf_length": len(sdf),
        "sdf_content": sdf,
    }

    if source == "2d":
        result["warning"] = ("Only 2D coordinates available. Use OpenBabel or RDKit "
                              "to generate 3D coordinates before antechamber.")

    if output_path:
        with open(output_path, 'w') as f:
            f.write(sdf)
        result["saved_to"] = output_path

    return result


def get_bioassay_summary(cid, target_name=None):
    """Get bioassay results for a compound.

    Returns activity data (IC50, EC50, Ki, etc.) that can be used
    to validate MD-computed binding free energies.
    """
    url = f"{PUBCHEM_API}/compound/cid/{cid}/assaysummary/JSON"
    result = _http_get(url)

    if "error" in result:
        return result

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


def get_similar_compounds(cid, threshold=90, max_results=10):
    """Find structurally similar compounds.

    Useful for:
    - Finding analogs for congeneric series FEP
    - Identifying related compounds with different activity
    - Building compound libraries for virtual screening validation
    """
    url = (f"{PUBCHEM_API}/compound/fastsimilarity_2d/cid/{cid}/cids/JSON"
           f"?Threshold={threshold}&MaxRecords={max_results}")
    result = _http_get(url)

    if "error" in result:
        return result

    cids = result.get("IdentifierList", {}).get("CID", [])
    if not cids:
        return {"cid": cid, "similar": []}

    # Get basic properties
    cid_list = ",".join(str(c) for c in cids[:max_results])
    props_url = (f"{PUBCHEM_API}/compound/cid/{cid_list}/property/"
                 f"MolecularFormula,MolecularWeight,CanonicalSMILES,IUPACName/JSON")
    props = _http_get(props_url)

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


# ─── MCP Protocol ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_compound",
        "description": "Search PubChem for compounds by name, SMILES, or InChI. Returns CID, SMILES, MW, LogP, charge, and other properties needed for MD parametrization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Compound name, SMILES, or InChI"},
                "search_type": {"type": "string", "enum": ["name", "smiles", "inchi"], "description": "Search type (default: name)"},
                "max_results": {"type": "integer", "description": "Max results (default: 5)"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_compound_properties",
        "description": "Get detailed compound properties by PubChem CID: SMILES, charge, LogP, TPSA, HBD/HBA, rotatable bonds. Includes MD-specific notes (charge for antechamber, flexibility assessment).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cid": {"type": "integer", "description": "PubChem CID"}
            },
            "required": ["cid"]
        }
    },
    {
        "name": "get_3d_conformer",
        "description": "Download 3D conformer as SDF. This is the starting geometry for antechamber ligand parametrization. Falls back to 2D if 3D unavailable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cid": {"type": "integer", "description": "PubChem CID"},
                "output_path": {"type": "string", "description": "Save SDF to this path (optional)"},
            },
            "required": ["cid"]
        }
    },
    {
        "name": "get_bioassay_summary",
        "description": "Get bioassay activity data (IC50, Ki, EC50) for a compound. Use to validate MD-computed binding free energies against experimental values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cid": {"type": "integer", "description": "PubChem CID"},
                "target_name": {"type": "string", "description": "Filter by target protein name (optional)"},
            },
            "required": ["cid"]
        }
    },
    {
        "name": "get_similar_compounds",
        "description": "Find structurally similar compounds. Useful for building congeneric series for FEP calculations or finding analogs with different activity profiles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cid": {"type": "integer", "description": "PubChem CID"},
                "threshold": {"type": "integer", "description": "Tanimoto similarity threshold 0-100 (default: 90)"},
                "max_results": {"type": "integer", "description": "Max results (default: 10)"},
            },
            "required": ["cid"]
        }
    },
]


def handle_tool_call(name, arguments):
    if name == "search_compound": return search_compound(**arguments)
    elif name == "get_compound_properties": return get_compound_properties(**arguments)
    elif name == "get_3d_conformer": return get_3d_conformer(**arguments)
    elif name == "get_bioassay_summary": return get_bioassay_summary(**arguments)
    elif name == "get_similar_compounds": return get_similar_compounds(**arguments)
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
                                       "serverInfo": {"name": "pubchem-server", "version": "1.0.0"},
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
        print("=== Search: erlotinib ===")
        print(json.dumps(search_compound("erlotinib", max_results=2), indent=2))
        print("\n=== Properties: CID 176870 (erlotinib) ===")
        print(json.dumps(get_compound_properties(176870), indent=2))
    else:
        run_mcp_server()

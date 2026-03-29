#!/usr/bin/env python3
"""
ChEMBL MCP Server for AmberMD Agent.

Local replacement for the remote mcp.deepsense.ai ChEMBL server.
Uses the public ChEMBL REST API directly — no external MCP relay, no timeouts.

Gives the agent experimental bioactivity intelligence:
- Search compounds by name → ChEMBL ID, SMILES, MW
- Get curated IC50 / Ki / EC50 binding data (for ΔG validation)
- Search biological targets
- Get mechanism of action for approved drugs
- Find drugs by therapeutic indication
- ADMET / drug-likeness properties

Run: python chembl_server.py
     python chembl_server.py --test
"""

import json
import sys
import math
import urllib.request
import urllib.parse

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"


def _http_get(url, retries=2):
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "AmberMD-Agent/1.0"}
    )
    last_error = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = resp.read().decode()
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return {"error": f"Non-JSON response: {data[:200]}"}
        except Exception as e:
            last_error = str(e)
            # Retry on timeout or 5xx; don't retry on 4xx
            if "404" in str(e) or "400" in str(e):
                break
    return {"error": last_error}


def _ki_to_dg(ki_nm, temperature_k=300.0):
    """Convert Ki in nM to ΔG in kcal/mol (ΔG = RT ln Ki).

    Sign convention: Ki in nM → Kd in M → ΔG = RT·ln(Kd).
    Result is negative for tight binders (binding is favourable).
    """
    if ki_nm is None or ki_nm <= 0:
        return None
    R = 1.987e-3  # kcal/(mol·K)
    kd_m = ki_nm * 1e-9
    dg = R * temperature_k * math.log(kd_m)
    return round(dg, 2)


def _format_molecule(mol):
    """Extract MD-relevant fields from a ChEMBL molecule record."""
    props = mol.get("molecule_properties") or {}
    struct = mol.get("molecule_structures") or {}
    # Prefer pref_name; fall back to first synonym
    name = mol.get("pref_name")
    if not name:
        syns = mol.get("molecule_synonyms") or []
        if syns:
            name = syns[0].get("molecule_synonym")
    return {
        "chembl_id": mol.get("molecule_chembl_id"),
        "name": name,
        "molecule_type": mol.get("molecule_type"),
        "max_phase": mol.get("max_phase"),  # 4 = approved drug
        "smiles": struct.get("canonical_smiles"),
        "inchi": struct.get("standard_inchi"),
        "inchikey": struct.get("standard_inchi_key"),
        "molecular_weight": props.get("full_mwt"),
        "alogp": props.get("alogp"),
        "hba": props.get("hba"),
        "hbd": props.get("hbd"),
        "psa": props.get("psa"),
        "rotatable_bonds": props.get("rtb"),
        "num_ro5_violations": props.get("num_ro5_violations"),
        "qed": props.get("qed_weighted"),
        "formal_charge": props.get("charge"),
        "heavy_atoms": props.get("heavy_atoms"),
    }


# ─── Tool Implementations ────────────────────────────────────────────────────

def compound_search(name, max_results=5):
    """Search ChEMBL for compounds by name.

    Searches preferred names and synonyms. Returns ChEMBL ID, SMILES,
    MW, charge, and drug approval phase. The ChEMBL ID is used by
    get_bioactivity() to retrieve experimental Ki/IC50 values.

    Args:
        name: Drug or compound name (e.g., "ritonavir", "erlotinib")
        max_results: Number of results to return (default: 5)
    """
    encoded = urllib.parse.quote(name)
    # Preferred name search first — returns canonical drug entries with pref_name set
    url = f"{CHEMBL_API}/molecule.json?pref_name__icontains={encoded}&limit={max_results}"
    result = _http_get(url)
    molecules = result.get("molecules", []) if "error" not in result else []

    if not molecules:
        # Fallback: synonym search via full-text endpoint
        url2 = f"{CHEMBL_API}/molecule/search.json?q={encoded}&limit={max_results}"
        result2 = _http_get(url2)
        if "error" not in result2:
            # Filter to entries that have a pref_name or synonym
            molecules = [m for m in result2.get("molecules", [])
                         if m.get("pref_name") or m.get("molecule_synonyms")]

    if not molecules and "error" in result:
        return result
    if not molecules:
        return {"query": name, "results": [], "message": "No compounds found in ChEMBL"}

    compounds = [_format_molecule(m) for m in molecules[:max_results]]
    return {"query": name, "results": compounds, "n_results": len(compounds)}


def get_bioactivity(compound, target=None, activity_type=None, max_results=20):
    """Get curated bioactivity data (Ki, IC50, EC50) from ChEMBL.

    This is the primary tool for validating MD-computed ΔG values.
    ChEMBL curates data from peer-reviewed literature — much more
    reliable than PubChem bioassay data for binding affinity validation.

    Workflow:
      1. compound_search("ritonavir") → get chembl_id = "CHEMBL163"
      2. get_bioactivity("CHEMBL163", target="HIV-1 protease")
         → Ki = 0.014 nM → ΔG = -14.0 kcal/mol

    Args:
        compound: ChEMBL ID (e.g., "CHEMBL163") or compound name
        target: Filter by target name substring (optional, e.g., "HIV protease")
        activity_type: Filter to specific measurement (e.g., "Ki", "IC50", "EC50")
        max_results: Max number of activities to return (default: 20)
    """
    # Resolve compound name → ChEMBL ID if needed
    chembl_id = compound
    if not compound.upper().startswith("CHEMBL"):
        search = compound_search(compound, max_results=1)
        results = search.get("results", [])
        if not results:
            return {"error": f"Could not find compound: {compound}"}
        chembl_id = results[0]["chembl_id"]
        compound_name = results[0]["name"]
    else:
        compound_name = compound

    # Filter to activities with pChEMBL values (curated, unit-normalised) and sort
    # by pChEMBL descending so the top-N are always the most potent/reliable hits
    params = f"molecule_chembl_id={chembl_id}&pchembl_value__isnull=false&order_by=-pchembl_value&limit={max_results}"
    if activity_type:
        params += f"&standard_type={urllib.parse.quote(activity_type)}"
    url = f"{CHEMBL_API}/activity.json?{params}"
    result = _http_get(url)

    if "error" in result:
        return result

    activities_raw = result.get("activities", [])
    activities = []
    for a in activities_raw:
        target_name = a.get("target_pref_name", "") or ""
        assay_desc = a.get("assay_description", "") or ""
        # Filter by target — check pref_name AND assay_description so gene symbols
        # like "EGFR" match even when pref_name is "Epidermal growth factor receptor"
        if target:
            t = target.lower()
            if t not in target_name.lower() and t not in assay_desc.lower():
                continue

        std_type = a.get("standard_type", "")
        std_value = a.get("standard_value")
        std_units = a.get("standard_units", "")
        relation = a.get("standard_relation", "=")

        # Convert Ki/Kd in nM → ΔG
        dg = None
        if std_type in ("Ki", "Kd") and std_units == "nM" and std_value:
            try:
                dg = _ki_to_dg(float(std_value))
            except (ValueError, TypeError):
                pass

        activities.append({
            "chembl_id": chembl_id,
            "target_name": target_name,
            "target_chembl_id": a.get("target_chembl_id"),
            "assay_chembl_id": a.get("assay_chembl_id"),
            "activity_type": std_type,
            "relation": relation,
            "value": std_value,
            "units": std_units,
            "pchembl_value": a.get("pchembl_value"),  # -log10(activity in M)
            "dg_kcal_mol": dg,
            "assay_type": a.get("assay_type"),
            "document_year": a.get("document_year"),
            "data_validity": a.get("data_validity_comment"),
        })

    return {
        "compound": compound_name,
        "chembl_id": chembl_id,
        "target_filter": target,
        "activity_type_filter": activity_type,
        "n_activities": len(activities),
        "activities": activities,
        "note": (
            "dg_kcal_mol is computed as RT·ln(Ki_M) at 300 K — negative means favourable binding. "
            "PMF from umbrella sampling is positive (work to unbind). Sign convention: ΔG_bind = -PMF_unbind."
        ),
    }


def target_search(name, organism="Homo sapiens", max_results=5):
    """Search ChEMBL for biological targets.

    Returns ChEMBL target IDs and classifications. The target_chembl_id
    can be used with get_bioactivity() to find all actives against a target.

    Args:
        name: Target protein name or gene symbol (e.g., "HIV-1 protease", "EGFR")
        organism: Filter by organism (default: "Homo sapiens")
        max_results: Number of results (default: 5)
    """
    encoded = urllib.parse.quote(name)
    url = f"{CHEMBL_API}/target.json?pref_name__icontains={encoded}&limit={max_results}"
    result = _http_get(url)

    if "error" in result:
        return result

    targets_raw = result.get("targets", [])
    targets = []
    for t in targets_raw:
        org = t.get("organism", "") or ""
        if organism and organism.lower() not in org.lower():
            # Also allow non-human targets for viral proteins etc
            if "homo sapiens" in org.lower() and organism.lower() != "homo sapiens":
                continue

        components = t.get("target_components", [])
        gene_names = []
        for comp in components:
            for syn in comp.get("target_component_synonyms", []):
                if syn.get("syn_type") == "GENE_SYMBOL":
                    gene_names.append(syn.get("component_synonym"))

        targets.append({
            "chembl_id": t.get("target_chembl_id"),
            "name": t.get("pref_name"),
            "type": t.get("target_type"),
            "organism": org,
            "gene_names": gene_names,
            "n_components": len(components),
        })

    # If organism filter left nothing, return all
    if not targets and organism:
        return target_search(name, organism="", max_results=max_results)

    return {"query": name, "organism": organism, "results": targets, "n_results": len(targets)}


def get_mechanism(drug):
    """Get mechanism of action for an approved drug.

    Returns binding mechanism, action type, and the primary target.
    Useful for understanding pharmacology before setting up MD.

    Args:
        drug: Drug name (e.g., "ritonavir") or ChEMBL ID
    """
    # Resolve to ChEMBL ID
    chembl_id = drug
    compound_name = drug
    if not drug.upper().startswith("CHEMBL"):
        search = compound_search(drug, max_results=1)
        results = search.get("results", [])
        if not results:
            return {"error": f"Could not find drug: {drug}"}
        chembl_id = results[0]["chembl_id"]
        compound_name = results[0]["name"]

    url = f"{CHEMBL_API}/mechanism.json?molecule_chembl_id={chembl_id}&limit=20"
    result = _http_get(url)

    if "error" in result:
        return result

    mechs_raw = result.get("mechanisms", [])
    mechanisms = []
    for m in mechs_raw:
        mechanisms.append({
            "target_chembl_id": m.get("target_chembl_id"),
            "target_name": m.get("target_name"),
            "action_type": m.get("action_type"),    # e.g. INHIBITOR, AGONIST
            "mechanism_of_action": m.get("mechanism_of_action"),
            "selectivity": m.get("selectivity_comment"),
            "direct_interaction": m.get("direct_interaction"),
            "disease_efficacy": m.get("disease_efficacy"),
            "references": [r.get("ref_id") for r in m.get("mechanism_refs", [])],
        })

    return {
        "drug": compound_name,
        "chembl_id": chembl_id,
        "n_mechanisms": len(mechanisms),
        "mechanisms": mechanisms,
    }


def drug_search(indication, max_results=10):
    """Find approved drugs by therapeutic indication.

    Searches ChEMBL drug indications (clinical trial and approval data).
    Useful for finding reference compounds in the same indication class.

    Args:
        indication: Disease or indication (e.g., "HIV", "lung cancer", "hypertension")
        max_results: Number of drugs to return (default: 10)
    """
    encoded = urllib.parse.quote(indication)
    # Try EFO term first (faster) then mesh heading
    url = (f"{CHEMBL_API}/drug_indication.json"
           f"?efo_term__icontains={encoded}&max_phase_for_ind__gte=3&limit={max_results}")
    result = _http_get(url)

    indications = result.get("drug_indications", []) if "error" not in result else []

    if not indications:
        url2 = (f"{CHEMBL_API}/drug_indication.json"
                f"?mesh_heading__icontains={encoded}&max_phase_for_ind__gte=3&limit={max_results}")
        result2 = _http_get(url2)
        indications = result2.get("drug_indications", []) if "error" not in result2 else []

    if not indications:
        return {"indication": indication, "n_drugs": 0, "drugs": [],
                "message": "No approved drugs found for this indication in ChEMBL"}

    drugs = []
    seen = set()

    for ind in indications:
        mol_id = ind.get("molecule_chembl_id")
        if mol_id in seen:
            continue
        seen.add(mol_id)

        drugs.append({
            "chembl_id": mol_id,
            "drug_name": ind.get("molecule_name"),
            "indication": ind.get("mesh_heading"),
            "efo_term": ind.get("efo_term"),
            "max_phase": ind.get("max_phase_for_ind"),
        })

    return {
        "indication": indication,
        "n_drugs": len(drugs),
        "drugs": drugs,
        "note": "max_phase=4 means FDA/EMA approved",
    }


def get_admet(compound):
    """Get ADMET (drug-likeness) properties for a compound.

    Returns Lipinski Ro5 descriptors, AlogP, PSA, QED score, and
    predicted CYP inhibition (where available). Use to assess
    whether a ligand is suitable for MD binding studies.

    Args:
        compound: ChEMBL ID (e.g., "CHEMBL163") or compound name
    """
    chembl_id = compound
    compound_name = compound
    if not compound.upper().startswith("CHEMBL"):
        search = compound_search(compound, max_results=1)
        results = search.get("results", [])
        if not results:
            return {"error": f"Could not find compound: {compound}"}
        chembl_id = results[0]["chembl_id"]
        compound_name = results[0]["name"]

    url = f"{CHEMBL_API}/molecule/{chembl_id}.json"
    result = _http_get(url)

    if "error" in result:
        return result

    props = result.get("molecule_properties") or {}
    struct = result.get("molecule_structures") or {}

    mw = float(props.get("full_mwt") or 0)
    hba = int(props.get("hba") or 0)
    hbd = int(props.get("hbd") or 0)
    alogp = float(props.get("alogp") or 0)
    ro5_violations = int(props.get("num_ro5_violations") or 0)

    # Lipinski rule-of-5 assessment
    ro5_checks = {
        "mw_le_500": mw <= 500,
        "hba_le_10": hba <= 10,
        "hbd_le_5": hbd <= 5,
        "alogp_le_5": alogp <= 5,
        "passes_ro5": ro5_violations == 0,
    }

    return {
        "compound": compound_name,
        "chembl_id": chembl_id,
        "smiles": struct.get("canonical_smiles"),
        "molecular_weight": mw,
        "alogp": alogp,
        "hba": hba,
        "hbd": hbd,
        "psa": props.get("psa"),
        "rotatable_bonds": props.get("rtb"),
        "heavy_atoms": props.get("heavy_atoms"),
        "formal_charge": props.get("charge"),
        "num_aromatic_rings": props.get("aromatic_rings"),
        "qed_weighted": props.get("qed_weighted"),
        "num_ro5_violations": ro5_violations,
        "lipinski_ro5": ro5_checks,
        "max_phase": result.get("max_phase"),
        "md_notes": {
            "charge_for_antechamber": props.get("charge", 0),
            "drug_like": ro5_violations == 0,
            "flexibility": (
                "high" if int(props.get("rtb") or 0) > 10 else
                "medium" if int(props.get("rtb") or 0) > 5 else "low"
            ),
            "note": (
                "Large, flexible ligands (MW>500, rtb>10) may need longer "
                "equilibration and wider sampling windows in umbrella sampling."
            ),
        },
    }


# ─── MCP Protocol ────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "compound_search",
        "description": (
            "Search ChEMBL for compounds by name. Returns ChEMBL ID, SMILES, MW, "
            "formal charge, and drug approval phase. Use the chembl_id returned here "
            "as input to get_bioactivity() to retrieve experimental Ki/IC50 values."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Compound or drug name (e.g., 'ritonavir', 'erlotinib')"},
                "max_results": {"type": "integer", "description": "Max results (default: 5)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_bioactivity",
        "description": (
            "Get curated experimental bioactivity data (Ki, IC50, EC50) from ChEMBL. "
            "PRIMARY tool for validating MD-computed ΔG. Automatically converts Ki in nM "
            "to ΔG_bind in kcal/mol. Pass a ChEMBL ID (from compound_search) or a drug name. "
            "Optionally filter by target name or activity type."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "compound": {"type": "string", "description": "ChEMBL ID (e.g., 'CHEMBL163') or compound name"},
                "target": {"type": "string", "description": "Filter by target name substring (e.g., 'HIV protease')"},
                "activity_type": {"type": "string", "description": "Filter to 'Ki', 'IC50', 'EC50', 'Kd', etc."},
                "max_results": {"type": "integer", "description": "Max activities to return (default: 20)"},
            },
            "required": ["compound"],
        },
    },
    {
        "name": "target_search",
        "description": (
            "Search ChEMBL for biological targets by name or gene symbol. "
            "Returns target ChEMBL IDs and classifications. Useful for finding "
            "the correct target to filter bioactivity data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Target name or gene symbol (e.g., 'HIV-1 protease', 'EGFR')"},
                "organism": {"type": "string", "description": "Organism filter (default: 'Homo sapiens'; use '' for all)"},
                "max_results": {"type": "integer", "description": "Max results (default: 5)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_mechanism",
        "description": (
            "Get mechanism of action for an approved drug: action type (inhibitor/agonist), "
            "target name, selectivity notes. Useful for understanding pharmacology "
            "before setting up an MD binding study."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "drug": {"type": "string", "description": "Drug name (e.g., 'ritonavir') or ChEMBL ID"},
            },
            "required": ["drug"],
        },
    },
    {
        "name": "drug_search",
        "description": (
            "Find FDA/EMA approved drugs by therapeutic indication. "
            "Useful for identifying reference compounds in the same drug class "
            "or for finding known binders to a target."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "indication": {"type": "string", "description": "Disease or indication (e.g., 'HIV', 'lung cancer')"},
                "max_results": {"type": "integer", "description": "Max drugs to return (default: 10)"},
            },
            "required": ["indication"],
        },
    },
    {
        "name": "get_admet",
        "description": (
            "Get ADMET and drug-likeness properties: Lipinski Ro5, AlogP, PSA, QED score, "
            "formal charge (for antechamber), flexibility assessment. "
            "Use to check suitability of a ligand for MD binding studies."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "compound": {"type": "string", "description": "ChEMBL ID or compound name"},
            },
            "required": ["compound"],
        },
    },
]


def handle_tool_call(name, arguments):
    if name == "compound_search":
        return compound_search(**arguments)
    elif name == "get_bioactivity":
        return get_bioactivity(**arguments)
    elif name == "target_search":
        return target_search(**arguments)
    elif name == "get_mechanism":
        return get_mechanism(**arguments)
    elif name == "drug_search":
        return drug_search(**arguments)
    elif name == "get_admet":
        return get_admet(**arguments)
    else:
        return {"error": f"Unknown tool: {name}"}


def run_mcp_server():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            request = json.loads(line.strip())
            method = request.get("method", "")

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "chembl-server", "version": "1.0.0"},
                        "capabilities": {"tools": {}},
                    },
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"tools": TOOLS},
                }
            elif method == "tools/call":
                params = request.get("params", {})
                result = handle_tool_call(params.get("name", ""), params.get("arguments", {}))
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
                }
            else:
                response = {"jsonrpc": "2.0", "id": request.get("id"), "result": {}}

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

        except (json.JSONDecodeError, EOFError):
            break
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("=== compound_search: ritonavir ===")
        r = compound_search("ritonavir", max_results=2)
        print(json.dumps(r, indent=2))

        chembl_id = (r.get("results") or [{}])[0].get("chembl_id", "CHEMBL163")
        print(f"\n=== get_bioactivity: {chembl_id} vs HIV protease ===")
        print(json.dumps(get_bioactivity(chembl_id, target="HIV", activity_type="Ki", max_results=5), indent=2))

        print(f"\n=== get_mechanism: ritonavir ===")
        print(json.dumps(get_mechanism("ritonavir"), indent=2))

        print(f"\n=== get_admet: ritonavir ===")
        print(json.dumps(get_admet("ritonavir"), indent=2))

        print(f"\n=== drug_search: HIV ===")
        print(json.dumps(drug_search("HIV", max_results=5), indent=2))
    else:
        run_mcp_server()

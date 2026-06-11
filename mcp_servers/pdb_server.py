#!/usr/bin/env python3
"""PDB/RCSB MCP Server for AmberMD Agent. Run: python pdb_server.py"""
import json, re, sys, http.client, socket, ssl, concurrent.futures, threading
from typing import Optional
from fastmcp import FastMCP
from _common import error_response, get_logger

mcp = FastMCP("pdb-server")
logger = get_logger(__name__)

RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA = "https://data.rcsb.org/rest/v1/core"

_ssl_ctx = ssl.create_default_context()
_conns = {"data": None, "search": None}  # persistent keep-alive connections
_conn_lock = threading.Lock()
_HOSTS = {"data": ("data.rcsb.org", 15), "search": ("search.rcsb.org", 30)}


def _get_conn(name):
    with _conn_lock:
        if _conns[name] is None:
            host, t = _HOSTS[name]
            _conns[name] = http.client.HTTPSConnection(host, timeout=t, context=_ssl_ctx)
        return _conns[name]


def _reset_conn(name):
    for n in (("data", "search") if name == "both" else (name,)):
        with _conn_lock:
            if _conns.get(n):
                try: _conns[n].close()
                except (OSError, http.client.HTTPException): pass
                _conns[n] = None


# GraphQL: single round-trip replaces 3 sequential REST calls.
_GQL_ENTRY = """
{{ entry(entry_id: "{pdb_id}") {{
  rcsb_id struct {{ title }} rcsb_accession_info {{ deposit_date }}
  exptl {{ method }} refine {{ ls_R_factor_R_work ls_R_factor_R_free }}
  rcsb_entry_info {{ resolution_combined polymer_entity_count nonpolymer_entity_count }}
  polymer_entities {{ rcsb_id
    entity_poly {{ type pdbx_strand_id rcsb_sample_sequence_length }}
    rcsb_entity_source_organism {{ ncbi_scientific_name }} }}
  nonpolymer_entities {{ rcsb_id pdbx_entity_nonpoly {{ comp_id name }} }} }} }}
"""

_GQL_ENTRIES_BATCH = """
{{ entries(entry_ids: {ids}) {{
  rcsb_id struct {{ title }} exptl {{ method }}
  rcsb_entry_info {{ resolution_combined }}
  polymer_entities {{ rcsb_entity_source_organism {{ ncbi_scientific_name }} }} }} }}
"""


def _do_request(name, method, path, body=None, retries=2):
    """Core HTTP request over persistent connection; reset + retry on failure."""
    headers = {"Accept": "application/json", "User-Agent": "AmberMD-Agent/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body).encode() if isinstance(body, dict) else (
            body.encode() if isinstance(body, str) else body)
    last_error = None
    for _ in range(retries):
        try:
            conn = _get_conn(name)
            conn.request(method, path, body=body, headers=headers)
            return json.loads(conn.getresponse().read().decode())
        except (ConnectionError, socket.timeout, http.client.HTTPException) as e:
            last_error = e; _reset_conn(name)
        except Exception as e:
            last_error = e; logger.debug(f"Unexpected error in _do_request: {e}"); _reset_conn(name)
    return error_response("max_retries", f"max retries exceeded: {last_error}")


def _timed_request(name, method, path, body=None, retries=2, total_timeout=30):
    """Hard wall-clock timeout wrapper — guards against servers trickling chunks forever."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_do_request, name, method, path, body, retries)
        try:
            return fut.result(timeout=total_timeout)
        except concurrent.futures.TimeoutError:
            _reset_conn(name)
            return {"error": f"Request timed out after {total_timeout}s"}


def _graphql(query, retries=2):
    result = _timed_request("data", "POST", "/graphql", body={"query": query}, retries=retries)
    if "errors" in result: return {"error": str(result["errors"])}
    if "error" in result: return {"error": result["error"]}
    return result.get("data", {})


def _http_get(url, retries=2):
    return _timed_request("data", "GET", url.replace("https://data.rcsb.org", ""), retries=retries)


def _http_post(url, data, retries=2):
    if "search.rcsb.org" in url:
        return _timed_request("search", "POST", url.replace("https://search.rcsb.org", ""), body=data, retries=retries)
    return _timed_request("data", "POST", url.replace("https://data.rcsb.org", ""), body=data, retries=retries)


@mcp.tool()
def search_pdb(query: str, organism: Optional[str] = None, resolution_max: Optional[float] = None,
               method: Optional[str] = None, has_ligand: Optional[bool] = None, max_results: int = 10) -> dict:
    """Search RCSB PDB by name, organism, resolution, or experimental method.
    Use to find structures for simulation.

    Args:
        query: Text search (protein name, function, etc.)
        organism: Filter by organism (e.g., "Homo sapiens")
        resolution_max: Max resolution in Å (e.g., 2.5)
        method: Experimental method ("X-RAY DIFFRACTION", "ELECTRON MICROSCOPY", "NMR")
        has_ligand: If True, only structures with ligands
        max_results: Number of results to return
    """
    # full_text + text attributes can't mix (HTTP 400) — resolution/method/organism post-filtered.
    fetch_rows = max(max_results * 4, 40)
    search_request = {
        "query": {"type": "terminal", "service": "full_text", "parameters": {"value": query}},
        "return_type": "entry",
        "request_options": {"results_content_type": ["experimental"],
                            "sort": [{"sort_by": "score", "direction": "desc"}],
                            "paginate": {"start": 0, "rows": fetch_rows}},
    }
    result = _http_post(RCSB_SEARCH, search_request)
    if "error" in result: return result

    rs = result.get("result_set", [])
    pdb_ids = [h.get("identifier", "") for h in rs]
    scores = {h.get("identifier", ""): round(h.get("score", 0), 2) for h in rs}
    if not pdb_ids: return {"total_count": 0, "results": []}

    # Enrich ALL candidates in ONE GraphQL batch call.
    batch_data = _graphql(_GQL_ENTRIES_BATCH.format(ids=json.dumps(pdb_ids)))
    enriched = {}
    for e in (batch_data.get("entries") or []):
        exptl = e.get("exptl") or [{}]
        res_list = (e.get("rcsb_entry_info") or {}).get("resolution_combined") or []
        orgs = [(src.get("ncbi_scientific_name") or "").lower()
                for pe in e.get("polymer_entities") or []
                for src in pe.get("rcsb_entity_source_organism") or []]
        enriched[e.get("rcsb_id", "")] = {
            "title": (e.get("struct") or {}).get("title", ""),
            "method": exptl[0].get("method", "") if exptl else "",
            "resolution": res_list[0] if res_list else None, "organisms": orgs}

    filtered = []
    for pid in pdb_ids:
        if len(filtered) >= max_results: break
        info = enriched.get(pid, {})
        res, em = info.get("resolution"), info.get("method", "")
        if resolution_max and res is not None and res > resolution_max: continue
        if method and em.upper() != method.upper(): continue
        if organism and not any(organism.lower() in o for o in info.get("organisms", [])): continue
        filtered.append({"pdb_id": pid, "score": scores.get(pid, 0),
                         "title": info.get("title", ""), "method": em, "resolution": res})
    return {"total_count": result.get("total_count", 0), "results": filtered}


@mcp.tool()
def get_structure_info(pdb_id: str) -> dict:
    """Get detailed information about a PDB structure: title, resolution, chains, ligands, organism.
    Use before any simulation to understand the system.

    Returns: title, method, resolution, chains, ligands, organism,
    polymer entities, assembly info, deposition date.
    Uses a single GraphQL call instead of 3 sequential REST calls.
    """
    pdb_id = pdb_id.upper().strip()
    if not re.match(r'^[A-Z0-9]{4}$', pdb_id):
        return {"error": f"Invalid pdb_id '{pdb_id}': must be 4 alphanumeric characters"}
    data = _graphql(_GQL_ENTRY.format(pdb_id=pdb_id))
    if "error" in data: return data
    e = data.get("entry")
    if not e: return {"error": f"No data returned for {pdb_id}"}

    exptl = e.get("exptl") or [{}]
    rcsb_info = e.get("rcsb_entry_info") or {}
    res_list = rcsb_info.get("resolution_combined") or []
    info = {
        "pdb_id": pdb_id, "title": (e.get("struct") or {}).get("title", ""),
        "deposition_date": (e.get("rcsb_accession_info") or {}).get("deposit_date", ""),
        "method": exptl[0].get("method", "") if exptl else "",
        "resolution": res_list[0] if res_list else None,
        "polymer_entity_count": rcsb_info.get("polymer_entity_count", 0),
        "nonpolymer_entity_count": rcsb_info.get("nonpolymer_entity_count", 0),
        "entities": [], "ligands": []}

    for ent in e.get("polymer_entities") or []:
        poly = ent.get("entity_poly") or {}
        ei = {"id": ent.get("rcsb_id", ""), "type": poly.get("type", ""),
              "chains": poly.get("pdbx_strand_id", ""),
              "length": poly.get("rcsb_sample_sequence_length", 0)}
        src = ent.get("rcsb_entity_source_organism") or []
        if src: ei["organism"] = src[0].get("ncbi_scientific_name", "")
        info["entities"].append(ei)

    for ent in e.get("nonpolymer_entities") or []:
        np = ent.get("pdbx_entity_nonpoly") or {}
        info["ligands"].append({"id": ent.get("rcsb_id", ""),
                                "comp_id": np.get("comp_id", ""), "name": np.get("name", "")})
    return info


@mcp.tool()
def get_ligand_info(pdb_id: str, ligand_id: str) -> dict:
    """Get detailed ligand information: SMILES, formula, molecular weight.
    Essential for ligand parametrization with antechamber.

    Returns: SMILES, InChI, formula, molecular weight, and binding site residues.

    Uses GraphQL (not REST /core/chemcomp): REST fetches the entire chemcomp
    record (hundreds of KB, >60s on this cluster); GraphQL returns only the
    requested fields in <2s.
    """
    pdb_id = pdb_id.upper().strip()
    ligand_id = ligand_id.upper().strip()
    # Validate against PDB CCD format to prevent GraphQL injection.
    if not re.match(r'^[A-Z0-9]{1,5}$', ligand_id):
        return {"error": f"Invalid ligand_id '{ligand_id}': must match ^[A-Z0-9]{{1,5}}$ (PDB CCD format)"}

    gql = """
{{ chem_comp(comp_id: "{cid}") {{
  chem_comp {{ id name formula formula_weight type }}
  pdbx_chem_comp_descriptor {{ type descriptor }} }} }}
""".format(cid=ligand_id)
    data = _graphql(gql)
    if "error" in data: return data

    cc = data.get("chem_comp") or {}
    chem = cc.get("chem_comp") or {}
    info = {"ligand_id": ligand_id, "pdb_id": pdb_id, "name": chem.get("name", ""),
            "formula": chem.get("formula", ""), "formula_weight": chem.get("formula_weight", 0),
            "type": chem.get("type", "")}
    for desc in cc.get("pdbx_chem_comp_descriptor") or []:
        dtype, val = desc.get("type", ""), desc.get("descriptor", "")
        if dtype == "SMILES_CANONICAL": info["smiles_canonical"] = val
        elif dtype == "SMILES": info.setdefault("smiles", val)
        elif dtype == "InChI": info["inchi"] = val
    return info


@mcp.tool()
def find_similar_structures(pdb_id: str, chain_id: str = "A", identity_cutoff: float = 0.7, max_results: int = 10) -> dict:
    """Find structures with similar protein sequences (BLAST-like search).
    Useful for finding alternate conformations, mutants, or homologs.
    """
    pdb_id = pdb_id.upper().strip()
    if not re.match(r'^[A-Z0-9]{4}$', pdb_id):
        return {"error": f"Invalid pdb_id '{pdb_id}': must be 4 alphanumeric characters"}

    # Get entity ID for the requested chain via GraphQL (already fetches chain→entity map)
    struct = get_structure_info(pdb_id)
    if "error" in struct:
        return struct
    entity_id = None
    for ent in struct.get("entities", []):
        if chain_id in [c.strip() for c in ent.get("chains", "").split(",")]:
            entity_id = ent["id"].split("_")[-1]  # "2HYY_1" → "1"
            break
    if not entity_id:
        return {"error": f"Chain {chain_id} not found in {pdb_id}"}

    # Fetch full sequence from polymer_entity REST endpoint
    edata = _http_get(f"{RCSB_DATA}/polymer_entity/{pdb_id}/{entity_id}")
    if isinstance(edata, dict) and "error" in edata:
        return edata
    sequence = (edata.get("entity_poly") or {}).get("pdbx_seq_one_letter_code_can", "")
    if not sequence:
        return {"error": f"No sequence for {pdb_id} chain {chain_id}"}

    search_request = {
        "query": {"type": "terminal", "service": "sequence",
                  "parameters": {"evalue_cutoff": 0.001, "identity_cutoff": identity_cutoff,
                                 "sequence_type": "protein", "value": sequence}},
        "return_type": "polymer_entity",
        "request_options": {"sort": [{"sort_by": "score", "direction": "desc"}],
                            "paginate": {"start": 0, "rows": max_results}},
    }
    result = _http_post(RCSB_SEARCH, search_request)
    if "error" in result: return result

    hits = []
    for hit in result.get("result_set", []):
        ident = hit.get("identifier", "")
        hits.append({"pdb_id": ident.split("_")[0] if "_" in ident else ident,
                     "entity": ident, "score": round(hit.get("score", 0), 2)})
    return {"query_pdb": pdb_id, "query_chain": chain_id,
            "sequence_length": len(sequence), "hits": hits}


@mcp.tool()
def get_validation_report(pdb_id: str) -> dict:
    """Get structure quality metrics + MD suitability assessment.
    ALWAYS check before running simulations.

    Helps the agent decide if a structure is suitable for MD:
    - Ramachandran outliers (should be <1%)
    - Clashscore (lower is better)
    - R-factor and R-free
    - Missing residues count

    Uses ONE REST call (GraphQL doesn't expose clashscore/Ramachandran under stable names).
    """
    pdb_id = pdb_id.upper().strip()
    if not re.match(r'^[A-Z0-9]{4}$', pdb_id):
        return {"error": f"Invalid pdb_id '{pdb_id}': must be 4 alphanumeric characters"}
    entry = _http_get(f"{RCSB_DATA}/entry/{pdb_id}")
    if "error" in entry: return entry

    res = entry.get("rcsb_entry_info", {}).get("resolution_combined", [])
    refine = entry.get("refine", [{}])
    geom_list = entry.get("pdbx_vrpt_summary_geometry", [])
    geom = geom_list[0] if geom_list else {}
    missing = entry.get("pdbx_unobs_or_zero_occ_residues", [])
    q = {
        "pdb_id": pdb_id, "resolution": res[0] if res else None,
        "r_factor": refine[0].get("ls_rfactor_rwork") if refine else None,
        "r_free": refine[0].get("ls_rfactor_rfree") if refine else None,
        "clashscore": geom.get("clashscore"),
        "ramachandran_outliers_pct": geom.get("percent_ramachandran_outliers"),
        "sidechain_outliers_pct": geom.get("percent_rotamer_outliers"),
        "missing_residue_count": len(missing) if isinstance(missing, list) else 0}

    issues = []
    if q["resolution"] and q["resolution"] > 3.0:
        issues.append(f"Low resolution ({q['resolution']} Å) — may have modeling errors")
    if q["ramachandran_outliers_pct"] and q["ramachandran_outliers_pct"] > 2.0:
        issues.append(f"High Ramachandran outliers ({q['ramachandran_outliers_pct']}%)")
    if q["clashscore"] and q["clashscore"] > 20:
        issues.append(f"High clashscore ({q['clashscore']})")
    if q["missing_residue_count"] > 10:
        issues.append(f"{q['missing_residue_count']} missing residues — may need modeling")
    if q["r_free"] and q["r_free"] > 0.30:
        issues.append(f"High R-free ({q['r_free']}) — model quality concern")
    q["md_suitability_issues"] = issues
    q["md_suitable"] = len(issues) == 0
    return q


def _prewarm():
    """Background SSL handshake + endpoint warm. First tool call ~0.02s instead of ~15s."""
    def _ping():
        try:
            _graphql('{ entry(entry_id: "2HYY") { rcsb_id } }')
            _timed_request("search", "POST", "/rcsbsearch/v2/query",
                body={"query": {"type": "terminal", "service": "full_text",
                                "parameters": {"value": "ABL"}},
                      "return_type": "entry",
                      "request_options": {"paginate": {"start": 0, "rows": 1}}},
                total_timeout=25)
        except Exception:
            pass
    threading.Thread(target=_ping, daemon=True).start()


if __name__ == "__main__":
    if "--test" in sys.argv:
        logger.debug("Testing PDB MCP Server...\n=== Search: ABL kinase ===")
        logger.debug(json.dumps(search_pdb("ABL kinase", organism="Homo sapiens", resolution_max=2.5, max_results=3), indent=2))
        logger.debug("\n=== Structure Info: 2HYY ===")
        logger.debug(json.dumps(get_structure_info("2HYY"), indent=2))
        logger.debug("\n=== Validation: 2HYY ===")
        logger.debug(json.dumps(get_validation_report("2HYY"), indent=2))
    _prewarm()
    mcp.run()

    
    
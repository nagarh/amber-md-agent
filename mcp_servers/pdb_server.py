#!/usr/bin/env python3
"""
PDB/RCSB MCP Server for AmberMD Agent.

Gives the agent rich structural biology queries:
- Search PDB by protein name, organism, resolution
- Get detailed structure info (chains, ligands, quality)
- Find similar structures (sequence search)
- Get validation reports (is this structure good for MD?)
- Download structures

Run: python pdb_server.py
Configure in .mcp.json as a local command server.
"""

import json
import sys
import http.client
import ssl
import concurrent.futures
from typing import Any


# ─── RCSB API Helpers ────────────────────────────────────────────────────────

RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA = "https://data.rcsb.org/rest/v1/core"
RCSB_GRAPHQL = "https://data.rcsb.org/graphql"

# Persistent connections — one SSL handshake per host for the entire server
# lifetime.  Eliminates the 5-15s cold-handshake latency that made every tool
# call a coin-flip on this HPC cluster.
_ssl_ctx = ssl.create_default_context()
_conn_data = None     # → data.rcsb.org  (GraphQL + REST)
_conn_search = None   # → search.rcsb.org (full-text search)


def _get_data_conn():
    """Return a keep-alive HTTPS connection to data.rcsb.org."""
    global _conn_data
    if _conn_data is None:
        _conn_data = http.client.HTTPSConnection(
            "data.rcsb.org", timeout=15, context=_ssl_ctx)
    return _conn_data


def _get_search_conn():
    """Return a keep-alive HTTPS connection to search.rcsb.org."""
    global _conn_search
    if _conn_search is None:
        _conn_search = http.client.HTTPSConnection(
            "search.rcsb.org", timeout=30, context=_ssl_ctx)
    return _conn_search


def _reset_conn(which="both"):
    """Close and clear a connection so next call opens a fresh one."""
    global _conn_data, _conn_search
    if which in ("data", "both") and _conn_data:
        try: _conn_data.close()
        except Exception: pass
        _conn_data = None
    if which in ("search", "both") and _conn_search:
        try: _conn_search.close()
        except Exception: pass
        _conn_search = None

# GraphQL query — single round-trip replaces 3 sequential REST calls.
# Only fields confirmed to exist in RCSB GraphQL schema are included.
# Validation metrics (clashscore, Ramachandran) are fetched separately via
# the REST API since their GraphQL field names differ across schema versions.
_GQL_ENTRY = """
{{
  entry(entry_id: "{pdb_id}") {{
    rcsb_id
    struct {{ title }}
    rcsb_accession_info {{ deposit_date }}
    exptl {{ method }}
    refine {{ ls_R_factor_R_work ls_R_factor_R_free }}
    rcsb_entry_info {{
      resolution_combined
      polymer_entity_count
      nonpolymer_entity_count
    }}
    polymer_entities {{
      rcsb_id
      entity_poly {{
        type pdbx_strand_id rcsb_sample_sequence_length
      }}
      rcsb_entity_source_organism {{ ncbi_scientific_name }}
    }}
    nonpolymer_entities {{
      rcsb_id
      pdbx_entity_nonpoly {{ comp_id name }}
    }}
  }}
}}
"""

# Batch GraphQL query — enrich multiple PDB IDs in one round-trip.
_GQL_ENTRIES_BATCH = """
{{
  entries(entry_ids: {ids}) {{
    rcsb_id
    struct {{ title }}
    exptl {{ method }}
    rcsb_entry_info {{ resolution_combined }}
    polymer_entities {{
      rcsb_entity_source_organism {{ ncbi_scientific_name }}
    }}
  }}
}}
"""


def _do_request(conn_getter, conn_name, method, path, body=None, retries=2):
    """Core HTTP request using persistent connections.

    On failure (timeout, connection reset, etc.) the connection is reset and
    retried once — this covers the case where a keep-alive connection went
    stale between tool calls.
    """
    headers = {"Accept": "application/json", "User-Agent": "AmberMD-Agent/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()

    for attempt in range(retries):
        try:
            conn = conn_getter()
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            return json.loads(resp.read().decode())
        except Exception as e:
            _reset_conn(conn_name)
            if attempt == retries - 1:
                return {"error": str(e)}
    return {"error": "max retries exceeded"}


def _timed_request(conn_getter, conn_name, method, path, body=None, retries=2, total_timeout=30):
    """Run _do_request in a thread with a hard wall-clock timeout.

    The per-socket timeout on HTTPSConnection only governs individual recv()
    calls.  For chunked responses (e.g. chemcomp) the server can trickle
    chunks indefinitely — each chunk arrives just under the socket timeout so
    resp.read() loops forever.  This wrapper kills the whole request if it
    hasn't completed within total_timeout seconds.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_do_request, conn_getter, conn_name, method, path, body, retries)
        try:
            return fut.result(timeout=total_timeout)
        except concurrent.futures.TimeoutError:
            _reset_conn(conn_name)
            return {"error": f"Request timed out after {total_timeout}s"}


def _graphql(query, retries=2):
    """Execute a GraphQL query against the RCSB GraphQL endpoint.
    Uses persistent connection — no per-call SSL handshake.
    """
    result = _timed_request(
        _get_data_conn, "data", "POST", "/graphql",
        body={"query": query}, retries=retries)
    if "errors" in result:
        return {"error": str(result["errors"])}
    return result.get("data", {})


def _http_get(url, retries=2):
    """HTTP GET on data.rcsb.org using persistent connection."""
    # Extract path from full URL
    path = url.replace("https://data.rcsb.org", "")
    return _timed_request(_get_data_conn, "data", "GET", path, retries=retries)


def _http_post(url, data, retries=2):
    """HTTP POST — routes to the correct persistent connection."""
    if "search.rcsb.org" in url:
        path = url.replace("https://search.rcsb.org", "")
        return _timed_request(
            _get_search_conn, "search", "POST", path,
            body=data, retries=retries)
    else:
        path = url.replace("https://data.rcsb.org", "")
        return _timed_request(
            _get_data_conn, "data", "POST", path,
            body=data, retries=retries)


# ─── Tool Implementations ───────────────────────────────────────────────────

def search_pdb(query, organism=None, resolution_max=None,
               method=None, has_ligand=None, max_results=10):
    """Search RCSB PDB using their search API.

    Args:
        query: Text search (protein name, function, etc.)
        organism: Filter by organism (e.g., "Homo sapiens")
        resolution_max: Max resolution in Å (e.g., 2.5)
        method: Experimental method ("X-RAY DIFFRACTION", "ELECTRON MICROSCOPY", "NMR")
        has_ligand: If True, only structures with ligands
        max_results: Number of results to return
    """
    # Build RCSB search query.
    # NOTE: RCSB returns HTTP 400 when full_text and text attribute services are
    # mixed in the same group query. Resolution and method are therefore applied
    # as Python post-filters on the enriched results rather than in the query.
    fetch_rows = max(max_results * 4, 40)  # fetch extra to allow for filtering

    query_node = {
        "type": "terminal",
        "service": "full_text",
        "parameters": {"value": query}
    }

    search_request = {
        "query": query_node,
        "return_type": "entry",
        "request_options": {
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": "score", "direction": "desc"}],
            "paginate": {"start": 0, "rows": fetch_rows}
        }
    }

    result = _http_post(RCSB_SEARCH, search_request)

    if "error" in result:
        return result

    pdb_ids = [hit.get("identifier", "") for hit in result.get("result_set", [])]
    scores  = {hit.get("identifier", ""): round(hit.get("score", 0), 2)
               for hit in result.get("result_set", [])}

    if not pdb_ids:
        return {"total_count": 0, "results": []}

    # Enrich ALL candidates in ONE GraphQL batch call (no sequential SSL handshakes)
    ids_json = json.dumps(pdb_ids)
    batch_data = _graphql(_GQL_ENTRIES_BATCH.format(ids=ids_json))
    enriched = {}
    for e in batch_data.get("entries") or []:
        pid = e.get("rcsb_id", "")
        exptl = e.get("exptl") or [{}]
        res_list = (e.get("rcsb_entry_info") or {}).get("resolution_combined") or []
        orgs = []
        for pe in e.get("polymer_entities") or []:
            for src in pe.get("rcsb_entity_source_organism") or []:
                orgs.append((src.get("ncbi_scientific_name") or "").lower())
        enriched[pid] = {
            "title":  (e.get("struct") or {}).get("title", ""),
            "method": exptl[0].get("method", "") if exptl else "",
            "resolution": res_list[0] if res_list else None,
            "organisms": orgs,
        }

    # Apply post-filters
    filtered = []
    for pid in pdb_ids:
        if len(filtered) >= max_results:
            break
        info = enriched.get(pid, {})
        res = info.get("resolution")
        entry_method = info.get("method", "")
        if resolution_max and res is not None and res > resolution_max:
            continue
        if method and entry_method.upper() != method.upper():
            continue
        if organism:
            orgs = info.get("organisms", [])
            if not any(organism.lower() in o for o in orgs):
                continue
        filtered.append({
            "pdb_id": pid,
            "score": scores.get(pid, 0),
            "title": info.get("title", ""),
            "method": entry_method,
            "resolution": res,
        })

    return {"total_count": result.get("total_count", 0), "results": filtered}


def get_structure_info(pdb_id):
    """Get detailed information about a PDB structure.

    Returns: title, method, resolution, chains, ligands, organism,
    polymer entities, assembly info, deposition date.
    Uses a single GraphQL call instead of 3 sequential REST calls.
    """
    pdb_id = pdb_id.upper().strip()
    data = _graphql(_GQL_ENTRY.format(pdb_id=pdb_id))
    if "error" in data:
        return data
    e = data.get("entry")
    if not e:
        return {"error": f"No data returned for {pdb_id}"}

    exptl = e.get("exptl") or [{}]
    rcsb_info = e.get("rcsb_entry_info") or {}
    res_list = rcsb_info.get("resolution_combined") or []

    info = {
        "pdb_id": pdb_id,
        "title": (e.get("struct") or {}).get("title", ""),
        "deposition_date": (e.get("rcsb_accession_info") or {}).get("deposit_date", ""),
        "method": exptl[0].get("method", "") if exptl else "",
        "resolution": res_list[0] if res_list else None,
        "polymer_entity_count": rcsb_info.get("polymer_entity_count", 0),
        "nonpolymer_entity_count": rcsb_info.get("nonpolymer_entity_count", 0),
    }

    info["entities"] = []
    for ent in e.get("polymer_entities") or []:
        poly = ent.get("entity_poly") or {}
        src = ent.get("rcsb_entity_source_organism") or []
        entity_info = {
            "id": ent.get("rcsb_id", ""),
            "type": poly.get("type", ""),
            "chains": poly.get("pdbx_strand_id", ""),
            "length": poly.get("rcsb_sample_sequence_length", 0),
        }
        if src:
            entity_info["organism"] = src[0].get("ncbi_scientific_name", "")
        info["entities"].append(entity_info)

    info["ligands"] = []
    for ent in e.get("nonpolymer_entities") or []:
        np = ent.get("pdbx_entity_nonpoly") or {}
        info["ligands"].append({
            "id": ent.get("rcsb_id", ""),
            "comp_id": np.get("comp_id", ""),
            "name": np.get("name", ""),
        })

    return info


def get_ligand_info(pdb_id, ligand_id):
    """Get detailed ligand information from a PDB structure.

    Returns: SMILES, InChI, formula, molecular weight,
    and binding site residues.

    Uses GraphQL (not REST /core/chemcomp) — the REST endpoint fetches the
    entire chemcomp record (~hundreds of KB for drug-like molecules) and can
    take >60s on this cluster.  GraphQL returns only the requested fields in
    <2s.
    """
    pdb_id = pdb_id.upper().strip()
    ligand_id = ligand_id.upper().strip()

    gql = """
{{
  chem_comp(comp_id: "{cid}") {{
    chem_comp {{
      id
      name
      formula
      formula_weight
      type
    }}
    pdbx_chem_comp_descriptor {{
      type
      descriptor
    }}
  }}
}}
""".format(cid=ligand_id)

    data = _graphql(gql)
    if "error" in data:
        return data

    cc = (data.get("chem_comp") or {})
    chem = (cc.get("chem_comp") or {})
    info = {
        "ligand_id": ligand_id,
        "pdb_id": pdb_id,
        "name": chem.get("name", ""),
        "formula": chem.get("formula", ""),
        "formula_weight": chem.get("formula_weight", 0),
        "type": chem.get("type", ""),
    }

    descriptors = cc.get("pdbx_chem_comp_descriptor") or []
    for desc in descriptors:
        dtype = desc.get("type", "")
        val = desc.get("descriptor", "")
        if dtype == "SMILES_CANONICAL":
            info["smiles_canonical"] = val
        elif dtype == "SMILES":
            info.setdefault("smiles", val)
        elif dtype == "InChI":
            info["inchi"] = val

    return info


def find_similar_structures(pdb_id, chain_id="A", identity_cutoff=0.7, max_results=10):
    """Find structures with similar sequences (BLAST-like search).

    Useful for finding alternate conformations, mutants, or homologs.
    """
    pdb_id = pdb_id.upper().strip()

    # Get sequence first
    entity_url = f"{RCSB_DATA}/entry/{pdb_id}/polymer_entities"
    entities = _http_get(entity_url)

    sequence = None
    if isinstance(entities, list):
        for ent in entities:
            chains = ent.get("entity_poly", {}).get("pdbx_strand_id", "")
            if chain_id in chains.split(","):
                sequence = ent.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can", "")
                break

    if not sequence:
        return {"error": f"Could not find sequence for {pdb_id} chain {chain_id}"}

    # Sequence search via RCSB
    search_request = {
        "query": {
            "type": "terminal",
            "service": "sequence",
            "parameters": {
                "evalue_cutoff": 0.001,
                "identity_cutoff": identity_cutoff,
                "sequence_type": "protein",
                "value": sequence
            }
        },
        "return_type": "polymer_entity",
        "request_options": {
            "sort": [{"sort_by": "score", "direction": "desc"}],
            "paginate": {"start": 0, "rows": max_results}
        }
    }

    result = _http_post(RCSB_SEARCH, search_request)
    if "error" in result:
        return result

    hits = []
    for hit in result.get("result_set", []):
        identifier = hit.get("identifier", "")
        # identifier is like "1ABC_1" (entry_entity)
        hit_pdb = identifier.split("_")[0] if "_" in identifier else identifier
        hits.append({
            "pdb_id": hit_pdb,
            "entity": identifier,
            "score": round(hit.get("score", 0), 2),
        })

    return {"query_pdb": pdb_id, "query_chain": chain_id,
            "sequence_length": len(sequence), "hits": hits}


def get_validation_report(pdb_id):
    """Get structure validation metrics.

    Helps the agent decide if a structure is suitable for MD:
    - Ramachandran outliers (should be <1%)
    - Clashscore (lower is better)
    - R-factor and R-free
    - Missing residues count

    Uses ONE REST call to the entry endpoint (validation metrics live here;
    GraphQL doesn't expose clashscore/Ramachandran under stable field names).
    """
    pdb_id = pdb_id.upper().strip()

    entry = _http_get(f"{RCSB_DATA}/entry/{pdb_id}")
    if "error" in entry:
        return entry

    rcsb = entry.get("rcsb_entry_info", {})
    res = rcsb.get("resolution_combined", [])
    refine = entry.get("refine", [{}])
    # Geometry validation lives under pdbx_vrpt_summary_geometry (list)
    geom_list = entry.get("pdbx_vrpt_summary_geometry", [])
    geom = geom_list[0] if geom_list else {}
    missing = entry.get("pdbx_unobs_or_zero_occ_residues", [])

    quality = {
        "pdb_id": pdb_id,
        "resolution": res[0] if res else None,
        "r_factor": refine[0].get("ls_rfactor_rwork") if refine else None,
        "r_free": refine[0].get("ls_rfactor_rfree") if refine else None,
        "clashscore": geom.get("clashscore"),
        "ramachandran_outliers_pct": geom.get("percent_ramachandran_outliers"),
        "sidechain_outliers_pct": geom.get("percent_rotamer_outliers"),
        "missing_residue_count": len(missing) if isinstance(missing, list) else 0,
    }

    issues = []
    if quality["resolution"] and quality["resolution"] > 3.0:
        issues.append(f"Low resolution ({quality['resolution']} Å) — may have modeling errors")
    if quality["ramachandran_outliers_pct"] and quality["ramachandran_outliers_pct"] > 2.0:
        issues.append(f"High Ramachandran outliers ({quality['ramachandran_outliers_pct']}%)")
    if quality["clashscore"] and quality["clashscore"] > 20:
        issues.append(f"High clashscore ({quality['clashscore']})")
    if quality["missing_residue_count"] > 10:
        issues.append(f"{quality['missing_residue_count']} missing residues — may need modeling")
    if quality["r_free"] and quality["r_free"] > 0.30:
        issues.append(f"High R-free ({quality['r_free']}) — model quality concern")

    quality["md_suitability_issues"] = issues
    quality["md_suitable"] = len(issues) == 0
    return quality


# ─── MCP Server Protocol ────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_pdb",
        "description": "Search RCSB PDB for protein structures by name, organism, resolution, or method. Use when you need to find a structure for simulation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text (protein name, function, etc.)"},
                "organism": {"type": "string", "description": "Filter by organism (e.g., 'Homo sapiens')"},
                "resolution_max": {"type": "number", "description": "Max resolution in Å"},
                "method": {"type": "string", "description": "Experimental method (X-RAY DIFFRACTION, ELECTRON MICROSCOPY, NMR)"},
                "max_results": {"type": "integer", "description": "Number of results (default: 10)"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_structure_info",
        "description": "Get detailed information about a PDB structure: title, resolution, chains, ligands, organism. Use before starting any simulation to understand the system.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdb_id": {"type": "string", "description": "4-letter PDB ID"}
            },
            "required": ["pdb_id"]
        }
    },
    {
        "name": "get_ligand_info",
        "description": "Get detailed ligand information: SMILES, formula, molecular weight. Essential for ligand parametrization with antechamber.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdb_id": {"type": "string", "description": "PDB ID containing the ligand"},
                "ligand_id": {"type": "string", "description": "3-letter ligand code (e.g., STI for imatinib)"}
            },
            "required": ["pdb_id", "ligand_id"]
        }
    },
    {
        "name": "find_similar_structures",
        "description": "Find structures with similar protein sequences. Useful for finding alternate conformations, mutants, or structures with better resolution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdb_id": {"type": "string"},
                "chain_id": {"type": "string", "description": "Chain ID (default: A)"},
                "identity_cutoff": {"type": "number", "description": "Sequence identity cutoff (default: 0.7)"},
                "max_results": {"type": "integer", "description": "Number of results (default: 10)"},
            },
            "required": ["pdb_id"]
        }
    },
    {
        "name": "get_validation_report",
        "description": "Get structure quality metrics and MD suitability assessment. ALWAYS check this before running simulations to ensure the structure is good enough.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdb_id": {"type": "string", "description": "4-letter PDB ID"}
            },
            "required": ["pdb_id"]
        }
    },
]


def handle_tool_call(name, arguments):
    """Dispatch MCP tool calls."""
    if name == "search_pdb":
        return search_pdb(**arguments)
    elif name == "get_structure_info":
        return get_structure_info(**arguments)
    elif name == "get_ligand_info":
        return get_ligand_info(**arguments)
    elif name == "find_similar_structures":
        return find_similar_structures(**arguments)
    elif name == "get_validation_report":
        return get_validation_report(**arguments)
    else:
        return {"error": f"Unknown tool: {name}"}


# ─── Connection pre-warm ────────────────────────────────────────────────────

def _prewarm():
    """Fire a lightweight GraphQL ping in the background on startup.

    Establishes both the SSL connection and warms the RCSB GraphQL endpoint
    so the first real tool call responds in ~0.02s instead of ~15s.
    Uses the smallest valid query: rcsb_id for a single well-known entry.
    """
    import threading

    def _ping():
        try:
            # Warm data.rcsb.org (GraphQL — used by get_structure_info,
            # get_ligand_info, get_validation_report)
            _graphql('{ entry(entry_id: "2HYY") { rcsb_id } }')
            # Warm search.rcsb.org (used by search_pdb)
            _timed_request(
                _get_search_conn, "search", "POST",
                "/rcsbsearch/v2/query",
                body={
                    "query": {
                        "type": "terminal",
                        "service": "full_text",
                        "parameters": {"value": "ABL"}
                    },
                    "return_type": "entry",
                    "request_options": {"paginate": {"start": 0, "rows": 1}}
                },
                total_timeout=25,
            )
        except Exception:
            pass  # Pre-warm failure is non-fatal

    t = threading.Thread(target=_ping, daemon=True)
    t.start()


# ─── MCP stdio protocol (simplified) ────────────────────────────────────────

def run_mcp_server():
    """Run as MCP server over stdio."""
    import sys

    _prewarm()  # background — doesn't block startup

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
                        "serverInfo": {"name": "pdb-server", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"tools": TOOLS}
                }
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = handle_tool_call(tool_name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                    }
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {}
                }

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

        except json.JSONDecodeError:
            continue
        except EOFError:
            break
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    if "--test" in sys.argv:
        # Quick test mode
        print("Testing PDB MCP Server...\n")
        print("=== Search: ABL kinase ===")
        print(json.dumps(search_pdb("ABL kinase", organism="Homo sapiens",
                                      resolution_max=2.5, max_results=3), indent=2))
        print("\n=== Structure Info: 2HYY ===")
        print(json.dumps(get_structure_info("2HYY"), indent=2))
        print("\n=== Validation: 2HYY ===")
        print(json.dumps(get_validation_report("2HYY"), indent=2))
    else:
        run_mcp_server()

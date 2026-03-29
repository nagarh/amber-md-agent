#!/usr/bin/env python3
"""
STRING-DB MCP Server for AmberMD Agent.

Gives the agent protein-protein interaction network intelligence:
- Find interaction partners for any target protein
- Get full PPI network for a set of proteins
- Functional enrichment (GO terms, KEGG pathways, Reactome)
- Map gene names to STRING IDs

Useful for:
- Identifying which proteins interact with your MD target
- Planning multi-target or allosteric simulations
- Contextualizing MD/binding results in pathway biology
- Finding off-targets for drug simulations

Run: python stringdb_server.py
     python stringdb_server.py --test
"""

import json
import sys
import urllib.request
import urllib.parse

STRING_API = "https://string-db.org/api/json"

ORGANISM_MAP = {
    "human": 9606,
    "homo sapiens": 9606,
    "mouse": 10090,
    "mus musculus": 10090,
    "rat": 10116,
    "rattus norvegicus": 10116,
    "yeast": 4932,
    "saccharomyces cerevisiae": 4932,
    "ecoli": 511145,
    "e. coli": 511145,
}


def _http_get(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "AmberMD-Agent/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def _resolve_organism(organism):
    """Convert organism name or taxon ID to integer taxon ID."""
    if isinstance(organism, int):
        return organism
    if str(organism).isdigit():
        return int(organism)
    return ORGANISM_MAP.get(organism.lower(), 9606)  # default human


# ─── Tool Implementations ────────────────────────────────────────────────────

def get_interaction_partners(protein, organism="human", limit=20, score_threshold=400):
    """Get proteins that interact with the query protein.

    Args:
        protein: Gene name or protein name (e.g., "EGFR", "TP53")
        organism: Species name or NCBI taxon ID (default: human)
        limit: Max number of interaction partners to return (default: 20)
        score_threshold: Minimum interaction score 0-1000 (default: 400 = medium confidence)
    """
    taxon = _resolve_organism(organism)
    params = urllib.parse.urlencode({
        "identifier": protein,
        "species": taxon,
        "limit": limit,
        "required_score": score_threshold,
        "caller_identity": "ambermd_agent"
    })
    url = f"{STRING_API}/interaction_partners?{params}"
    result = _http_get(url)

    if "error" in result or not isinstance(result, list):
        return {"error": result.get("error", "No results"), "protein": protein}

    partners = []
    for entry in result:
        partners.append({
            "partner": entry.get("preferredName_B", entry.get("stringId_B", "")),
            "string_id": entry.get("stringId_B", ""),
            "score": entry.get("score", 0),
            "nscore": entry.get("nscore", 0),   # neighborhood score
            "fscore": entry.get("fscore", 0),   # fusion score
            "pscore": entry.get("pscore", 0),   # phylogenetic score
            "ascore": entry.get("ascore", 0),   # co-expression score
            "escore": entry.get("escore", 0),   # experimental score
            "dscore": entry.get("dscore", 0),   # database score
            "tscore": entry.get("tscore", 0),   # text-mining score
        })

    return {
        "query": protein,
        "organism": organism,
        "taxon_id": taxon,
        "score_threshold": score_threshold,
        "n_partners": len(partners),
        "partners": partners,
        "md_relevance": (
            "High-scoring partners (escore > 0.7) are experimentally validated interactors "
            "— consider these for protein-protein interface simulations or allosteric studies."
        )
    }


def get_network(proteins, organism="human", score_threshold=400):
    """Get the interaction network for a set of proteins.

    Returns all interactions between the provided proteins and their
    immediate neighbors, with confidence scores.

    Args:
        proteins: List of gene/protein names (e.g., ["EGFR", "KRAS", "SRC"])
        organism: Species name or NCBI taxon ID (default: human)
        score_threshold: Minimum interaction score 0-1000 (default: 400)
    """
    taxon = _resolve_organism(organism)
    identifiers = "%0d".join(proteins)  # STRING uses %0d as separator
    params = urllib.parse.urlencode({
        "identifiers": identifiers,
        "species": taxon,
        "required_score": score_threshold,
        "caller_identity": "ambermd_agent"
    })
    url = f"{STRING_API}/network?{params}"
    result = _http_get(url)

    if "error" in result or not isinstance(result, list):
        return {"error": result.get("error", "No results"), "proteins": proteins}

    interactions = []
    for entry in result:
        interactions.append({
            "protein_a": entry.get("preferredName_A", ""),
            "protein_b": entry.get("preferredName_B", ""),
            "score": entry.get("score", 0),
            "experimental_score": entry.get("escore", 0),
        })

    # Build adjacency summary
    nodes = set()
    for i in interactions:
        nodes.add(i["protein_a"])
        nodes.add(i["protein_b"])

    return {
        "query_proteins": proteins,
        "organism": organism,
        "taxon_id": taxon,
        "score_threshold": score_threshold,
        "n_nodes": len(nodes),
        "n_interactions": len(interactions),
        "nodes": sorted(nodes),
        "interactions": interactions,
    }


def get_functional_enrichment(proteins, organism="human"):
    """Get functional enrichment analysis for a set of proteins.

    Returns enriched GO terms (biological process, molecular function,
    cellular component), KEGG pathways, and Reactome pathways.

    Args:
        proteins: List of gene/protein names
        organism: Species name or NCBI taxon ID (default: human)
    """
    taxon = _resolve_organism(organism)
    identifiers = "%0d".join(proteins)
    params = urllib.parse.urlencode({
        "identifiers": identifiers,
        "species": taxon,
        "caller_identity": "ambermd_agent"
    })
    url = f"{STRING_API}/enrichment?{params}"
    result = _http_get(url)

    if "error" in result or not isinstance(result, list):
        return {"error": result.get("error", "No results"), "proteins": proteins}

    enriched = {"GO_biological_process": [], "GO_molecular_function": [],
                "GO_cellular_component": [], "KEGG": [], "Reactome": [], "other": []}

    for entry in result:
        category = entry.get("category", "other")
        item = {
            "term_id": entry.get("term", ""),
            "description": entry.get("description", ""),
            "p_value": entry.get("p_value", 1.0),
            "fdr": entry.get("fdr", 1.0),
            "proteins_in_term": entry.get("inputGenes", ""),
            "n_proteins": entry.get("number_of_genes", 0),
        }
        if category in enriched:
            enriched[category].append(item)
        else:
            enriched["other"].append(item)

    # Sort each category by FDR
    for cat in enriched:
        enriched[cat].sort(key=lambda x: x["fdr"])
        enriched[cat] = enriched[cat][:10]  # Top 10 per category

    return {
        "query_proteins": proteins,
        "organism": organism,
        "enrichment": enriched,
    }


def map_protein_ids(proteins, organism="human"):
    """Map gene/protein names to STRING IDs.

    Useful to verify that STRING recognizes the protein names you're
    using before running network or enrichment queries.

    Args:
        proteins: List of gene/protein names
        organism: Species name or NCBI taxon ID (default: human)
    """
    taxon = _resolve_organism(organism)
    identifiers = "%0d".join(proteins)
    params = urllib.parse.urlencode({
        "identifiers": identifiers,
        "species": taxon,
        "caller_identity": "ambermd_agent"
    })
    url = f"{STRING_API}/get_string_ids?{params}"
    result = _http_get(url)

    if "error" in result or not isinstance(result, list):
        return {"error": result.get("error", "No results"), "proteins": proteins}

    mapped = []
    for entry in result:
        mapped.append({
            "query": entry.get("queryItem", ""),
            "string_id": entry.get("stringId", ""),
            "preferred_name": entry.get("preferredName", ""),
            "annotation": entry.get("annotation", ""),
            "taxon_id": entry.get("ncbiTaxonId", taxon),
        })

    return {"organism": organism, "taxon_id": taxon, "mapped": mapped}


# ─── MCP Protocol ─────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_interaction_partners",
        "description": (
            "Find proteins that interact with a query protein in STRING-DB. "
            "Returns interaction partners with confidence scores broken down by evidence type "
            "(experimental, database, co-expression, text-mining). "
            "Use to identify proteins that physically interact with your MD target — "
            "relevant for protein-protein interface simulations and allosteric studies."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "protein": {"type": "string", "description": "Gene or protein name (e.g. 'EGFR', 'TP53')"},
                "organism": {"type": "string", "description": "Species name or NCBI taxon ID (default: human)"},
                "limit": {"type": "integer", "description": "Max interaction partners to return (default: 20)"},
                "score_threshold": {"type": "integer", "description": "Min score 0-1000: 400=medium, 700=high, 900=highest confidence (default: 400)"},
            },
            "required": ["protein"]
        }
    },
    {
        "name": "get_network",
        "description": (
            "Get the protein-protein interaction network for a set of proteins. "
            "Returns all interactions between the proteins and their neighbors. "
            "Use to understand the interaction landscape around your target "
            "or to plan multi-protein simulation systems."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "proteins": {"type": "array", "items": {"type": "string"}, "description": "List of gene/protein names"},
                "organism": {"type": "string", "description": "Species name or NCBI taxon ID (default: human)"},
                "score_threshold": {"type": "integer", "description": "Min interaction score 0-1000 (default: 400)"},
            },
            "required": ["proteins"]
        }
    },
    {
        "name": "get_functional_enrichment",
        "description": (
            "Get GO term and pathway enrichment for a list of proteins. "
            "Returns enriched biological processes, molecular functions, "
            "KEGG pathways, and Reactome pathways with FDR-corrected p-values. "
            "Use to understand the biological context of your simulation target "
            "or to interpret a set of proteins identified from MD analysis."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "proteins": {"type": "array", "items": {"type": "string"}, "description": "List of gene/protein names"},
                "organism": {"type": "string", "description": "Species name or NCBI taxon ID (default: human)"},
            },
            "required": ["proteins"]
        }
    },
    {
        "name": "map_protein_ids",
        "description": (
            "Map gene/protein names to STRING IDs to verify STRING recognizes them. "
            "Run this first if get_interaction_partners or get_network returns no results."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "proteins": {"type": "array", "items": {"type": "string"}, "description": "List of gene/protein names"},
                "organism": {"type": "string", "description": "Species name or NCBI taxon ID (default: human)"},
            },
            "required": ["proteins"]
        }
    },
]


def handle_tool_call(name, arguments):
    if name == "get_interaction_partners": return get_interaction_partners(**arguments)
    elif name == "get_network":             return get_network(**arguments)
    elif name == "get_functional_enrichment": return get_functional_enrichment(**arguments)
    elif name == "map_protein_ids":         return map_protein_ids(**arguments)
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
                                       "serverInfo": {"name": "stringdb-server", "version": "1.0.0"},
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
        print("=== Interaction partners: EGFR ===")
        print(json.dumps(get_interaction_partners("EGFR", limit=5), indent=2))
        print("\n=== Functional enrichment: EGFR, KRAS, SRC ===")
        print(json.dumps(get_functional_enrichment(["EGFR", "KRAS", "SRC"]), indent=2))
    else:
        run_mcp_server()

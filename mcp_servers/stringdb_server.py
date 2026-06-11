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
from typing import List, Union

from fastmcp import FastMCP
from _common import http_get, error_response, get_logger

logger = get_logger(__name__)

mcp = FastMCP("stringdb-server")

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

_PROTEIN_SEPARATOR = "%0d"


def _resolve_organism(organism):
    """Convert organism name or taxon ID to integer taxon ID.
    M-19 fix: unknown organism raises ValueError instead of silently defaulting to human.
    """
    if isinstance(organism, int):
        return organism
    if str(organism).isdigit():
        return int(organism)
    key = organism.lower()
    if key not in ORGANISM_MAP:
        raise ValueError(
            f"Unknown organism '{organism}'. Supported names: {list(ORGANISM_MAP.keys())}. "
            f"Or pass a numeric NCBI taxon ID."
        )
    return ORGANISM_MAP[key]


# ─── Tool Implementations ────────────────────────────────────────────────────

@mcp.tool()
def get_interaction_partners(protein: str, organism: Union[str, int] = "human", limit: int = 20, score_threshold: int = 400) -> dict:
    """Find proteins that interact with a query protein in STRING-DB.
    Returns partners + scores (experimental, database, co-expression, text-mining).

    Args:
        protein: Gene name or protein name (e.g., "EGFR", "TP53")
        organism: Species name or NCBI taxon ID (default: human)
        limit: Max number of interaction partners to return (default: 20)
        score_threshold: Minimum interaction score 0-1000 (default: 400 = medium confidence)
    """
    # M-20 fix: score_threshold bounds check
    if not (0 <= score_threshold <= 1000):
        return {"error": f"score_threshold must be 0-1000, got {score_threshold}",
                "query": protein, "partners": [], "n_partners": 0}
    # M-21 fix: limit bounds check
    if limit <= 0:
        return {"error": f"limit must be > 0, got {limit}",
                "query": protein, "partners": [], "n_partners": 0}
    try:
        taxon = _resolve_organism(organism)
    except ValueError as e:
        # M-23 fix: error shape must match success shape — use "query" + "taxon_id" like success
        return {"error": str(e), "query": protein, "taxon_id": None,
                "partners": [], "n_partners": 0}
    params = urllib.parse.urlencode({
        "identifier": protein,
        "species": taxon,
        "limit": limit,
        "required_score": score_threshold,
        "caller_identity": "ambermd_agent"
    })
    url = f"{STRING_API}/interaction_partners?{params}"
    result = http_get(url)

    # M-23 fix: error response must include same top-level keys as success response
    if isinstance(result, dict) and "error" in result:
        return {"error": result.get("error", "No results"), "query": protein,
                "taxon_id": taxon, "partners": [], "n_partners": 0}
    if not isinstance(result, list):
        return {"error": "No results", "query": protein, "taxon_id": taxon,
                "partners": [], "n_partners": 0}

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


@mcp.tool()
def get_network(proteins: List[str], organism: Union[str, int] = "human", score_threshold: int = 400) -> dict:
    """Protein-protein interaction network for a set of proteins.
    Returns all interactions between proteins + neighbors.

    Returns all interactions between the provided proteins and their
    immediate neighbors, with confidence scores.

    Args:
        proteins: List of gene/protein names (e.g., ["EGFR", "KRAS", "SRC"])
        organism: Species name or NCBI taxon ID (default: human)
        score_threshold: Minimum interaction score 0-1000 (default: 400)
    """
    # M-22 fix: empty proteins list guard
    if not proteins:
        return {"error": "proteins list must not be empty", "proteins": [],
                "query_proteins": [], "nodes": [], "interactions": [], "n_nodes": 0, "n_interactions": 0}
    try:
        taxon = _resolve_organism(organism)
    except ValueError as e:
        return {"error": str(e), "proteins": proteins, "query_proteins": proteins,
                "nodes": [], "interactions": [], "n_nodes": 0, "n_interactions": 0}
    identifiers = _PROTEIN_SEPARATOR.join(proteins)
    params = urllib.parse.urlencode({
        "identifiers": identifiers,
        "species": taxon,
        "required_score": score_threshold,
        "caller_identity": "ambermd_agent"
    })
    url = f"{STRING_API}/network?{params}"
    result = http_get(url)

    # H-24 fix: error response must include same top-level keys as success response
    # with empty defaults, so callers can safely unpack result["interactions"] etc.
    if isinstance(result, dict) and "error" in result:
        return {
            "error": result.get("error", "No results"),
            "proteins": proteins,
            "query_proteins": proteins,
            "nodes": [],
            "interactions": [],
            "n_nodes": 0,
            "n_interactions": 0,
        }
    if not isinstance(result, list):
        return {
            "error": "No results",
            "proteins": proteins,
            "query_proteins": proteins,
            "nodes": [],
            "interactions": [],
            "n_nodes": 0,
            "n_interactions": 0,
        }

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


@mcp.tool()
def get_functional_enrichment(proteins: List[str], organism: Union[str, int] = "human") -> dict:
    """GO term + pathway enrichment for a list of proteins.
    Returns enriched BP/MF/CC, KEGG, Reactome with FDR-corrected p-values.

    Returns enriched GO terms (biological process, molecular function,
    cellular component), KEGG pathways, and Reactome pathways.

    Args:
        proteins: List of gene/protein names
        organism: Species name or NCBI taxon ID (default: human)
    """
    _EMPTY_ENRICHMENT_2 = {
        "GO_biological_process": [], "GO_molecular_function": [],
        "GO_cellular_component": [], "KEGG": [], "Reactome": [], "other": [],
    }
    # M-22 fix: empty proteins list guard
    if not proteins:
        return {"error": "proteins list must not be empty", "proteins": [],
                "enrichment": _EMPTY_ENRICHMENT_2}
    try:
        taxon = _resolve_organism(organism)
    except ValueError as e:
        return {"error": str(e), "proteins": proteins, "enrichment": _EMPTY_ENRICHMENT_2}
    identifiers = _PROTEIN_SEPARATOR.join(proteins)
    params = urllib.parse.urlencode({
        "identifiers": identifiers,
        "species": taxon,
        "caller_identity": "ambermd_agent"
    })
    url = f"{STRING_API}/enrichment?{params}"
    result = http_get(url)

    # H-25 fix: error response must include "enrichment" key with empty defaults
    # so callers don't KeyError when unpacking result["enrichment"].
    _EMPTY_ENRICHMENT = {
        "GO_biological_process": [], "GO_molecular_function": [],
        "GO_cellular_component": [], "KEGG": [], "Reactome": [], "other": [],
    }
    if isinstance(result, dict) and "error" in result:
        return {
            "error": result.get("error", "No results"),
            "proteins": proteins,
            "enrichment": _EMPTY_ENRICHMENT,
        }
    if not isinstance(result, list):
        return {
            "error": "No results",
            "proteins": proteins,
            "enrichment": _EMPTY_ENRICHMENT,
        }

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


@mcp.tool()
def map_protein_ids(proteins: List[str], organism: Union[str, int] = "human") -> dict:
    """Map gene/protein names to STRING IDs.
    Run first if get_interaction_partners or get_network returns no results.

    Useful to verify that STRING recognizes the protein names you're
    using before running network or enrichment queries.

    Args:
        proteins: List of gene/protein names
        organism: Species name or NCBI taxon ID (default: human)
    """
    # M-22 fix: empty proteins list guard (M-24 — map_protein_ids)
    if not proteins:
        return {"error": "proteins list must not be empty", "proteins": [], "mapped": []}
    try:
        taxon = _resolve_organism(organism)
    except ValueError as e:
        # M-25: unknown organism guard for map_protein_ids
        return {"error": str(e), "proteins": proteins, "mapped": []}
    identifiers = _PROTEIN_SEPARATOR.join(proteins)
    params = urllib.parse.urlencode({
        "identifiers": identifiers,
        "species": taxon,
        "caller_identity": "ambermd_agent"
    })
    url = f"{STRING_API}/get_string_ids?{params}"
    result = http_get(url)

    if isinstance(result, dict) and "error" in result:
        return {"error": result.get("error", "No results"), "proteins": proteins, "mapped": []}
    if not isinstance(result, list):
        return {"error": "No results", "proteins": proteins, "mapped": []}

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


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("=== Interaction partners: EGFR ===")
        print(json.dumps(get_interaction_partners("EGFR", limit=5), indent=2))
        print("\n=== Functional enrichment: EGFR, KRAS, SRC ===")
        print(json.dumps(get_functional_enrichment(["EGFR", "KRAS", "SRC"]), indent=2))
    else:
        mcp.run()

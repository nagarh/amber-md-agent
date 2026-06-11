#!/usr/bin/env python3
"""
UniProt MCP Server for AmberMD Agent.

Gives the agent deep protein biology knowledge:
- Search proteins by name, gene, organism
- Get full sequences, domains, active sites
- Find disease-associated mutations (for WT vs mutant simulations)
- Post-translational modifications (critical for accurate MD setup)
- Cross-references to PDB, AlphaFold, Pfam
- Isoform information

Run: python uniprot_server.py
     python uniprot_server.py --test
"""

import json
import sys
import urllib.request
import urllib.parse
from typing import Optional

from fastmcp import FastMCP
from _common import http_get, http_get_text, error_response, get_logger

mcp = FastMCP("uniprot-server")
logger = get_logger(__name__)

UNIPROT_API = "https://rest.uniprot.org"


# ─── Tool Implementations ───────────────────────────────────────────────────

@mcp.tool()
def search_protein(query: str, organism: Optional[str] = None, max_results: int = 10) -> dict:
    """Search UniProt for proteins by name, gene, or keyword.
    Returns accession IDs, names, organisms, sequence lengths.

    Args:
        query: Protein name, gene name, or keyword (e.g., "EGFR", "kinase", "insulin receptor")
        organism: Filter by organism (e.g., "Homo sapiens", "9606" for taxon ID)
        max_results: Number of results to return
    """
    search_parts = [query]
    if organism:
        if organism.isdigit():
            search_parts.append(f"AND organism_id:{organism}")
        else:
            search_parts.append(f'AND organism_name:"{organism}"')

    search_query = " ".join(search_parts)
    params = urllib.parse.urlencode({
        "query": search_query,
        "format": "json",
        "size": max_results,
        "fields": "accession,id,protein_name,gene_names,organism_name,length,reviewed"
    })

    result = http_get(f"{UNIPROT_API}/uniprotkb/search?{params}")
    if "error" in result:
        return result

    entries = []
    for r in result.get("results", []):
        protein_name = ""
        pn = r.get("proteinDescription", {})
        rec = pn.get("recommendedName", {})
        if rec:
            protein_name = rec.get("fullName", {}).get("value", "")
        elif pn.get("submissionNames"):
            protein_name = pn["submissionNames"][0].get("fullName", {}).get("value", "")

        genes = r.get("genes", [])
        gene_name = genes[0].get("geneName", {}).get("value", "") if genes else ""

        entries.append({
            "accession": r.get("primaryAccession", ""),
            "entry_name": r.get("uniProtkbId", ""),
            "protein_name": protein_name,
            "gene": gene_name,
            "organism": r.get("organism", {}).get("scientificName", ""),
            "length": r.get("sequence", {}).get("length", 0),
            "reviewed": r.get("entryType", "") == "UniProtKB reviewed (Swiss-Prot)",
        })

    return {"query": query, "total": len(entries), "results": entries}


@mcp.tool()
def get_protein_info(accession: str) -> dict:
    """Get comprehensive protein info: function, sequence, domains, active sites, PTMs, disulfide bonds,
    transmembrane regions, PDB cross-refs, AlphaFold ID. Includes MD-relevant notes (CYX, PTMs, membrane).

    Returns: name, function, sequence, domains, active sites,
    binding sites, post-translational modifications, subcellular location,
    cross-references to PDB and AlphaFold.
    """
    # M-26 fix: URL-encode accession to prevent path injection (e.g. "../admin")
    safe_accession = urllib.parse.quote(accession, safe="")
    result = http_get(f"{UNIPROT_API}/uniprotkb/{safe_accession}.json")
    if "error" in result:
        return result

    # Basic info
    pn = result.get("proteinDescription", {})
    rec = pn.get("recommendedName", {})
    protein_name = rec.get("fullName", {}).get("value", "") if rec else ""

    genes = result.get("genes", [])
    gene_name = genes[0].get("geneName", {}).get("value", "") if genes else ""

    info = {
        "accession": accession,
        "protein_name": protein_name,
        "gene": gene_name,
        "organism": result.get("organism", {}).get("scientificName", ""),
        "length": result.get("sequence", {}).get("length", 0),
        "sequence": result.get("sequence", {}).get("value", ""),
    }

    # Function description
    comments = result.get("comments", [])
    for comment in comments:
        ctype = comment.get("commentType", "")
        if ctype == "FUNCTION":
            texts = comment.get("texts", [])
            if texts:
                info["function"] = texts[0].get("value", "")
        elif ctype == "SUBCELLULAR LOCATION":
            locs = comment.get("subcellularLocations", [])
            info["subcellular_location"] = [
                loc.get("location", {}).get("value", "")
                for loc in locs if loc.get("location")
            ]
        elif ctype == "SUBUNIT":
            texts = comment.get("texts", [])
            if texts:
                info["subunit"] = texts[0].get("value", "")

    # Features: domains, active sites, binding sites, PTMs
    features = result.get("features", [])
    info["domains"] = []
    info["active_sites"] = []
    info["binding_sites"] = []
    info["ptm"] = []
    info["disulfide_bonds"] = []
    info["signal_peptide"] = None
    info["transmembrane"] = []

    for feat in features:
        ftype = feat.get("type", "")
        loc = feat.get("location", {})
        start = loc.get("start", {}).get("value")
        end = loc.get("end", {}).get("value")
        desc = feat.get("description", "")

        entry = {"type": ftype, "start": start, "end": end, "description": desc}

        if ftype == "Domain":
            info["domains"].append(entry)
        elif ftype == "Active site":
            info["active_sites"].append(entry)
        elif ftype == "Binding site":
            info["binding_sites"].append(entry)
        elif ftype in ("Modified residue", "Glycosylation", "Lipidation"):
            info["ptm"].append(entry)
        elif ftype == "Disulfide bond":
            info["disulfide_bonds"].append(entry)
        elif ftype == "Signal peptide":
            info["signal_peptide"] = entry
        elif ftype == "Transmembrane":
            info["transmembrane"].append(entry)

    # Cross-references to PDB
    xrefs = result.get("uniProtKBCrossReferences", [])
    info["pdb_entries"] = []
    info["alphafold_id"] = None

    for xref in xrefs:
        db = xref.get("database", "")
        if db == "PDB":
            pdb_entry = {
                "pdb_id": xref.get("id", ""),
                "method": "",
                "resolution": "",
                "chains": "",
            }
            for prop in xref.get("properties", []):
                key = prop.get("key", "")
                val = prop.get("value", "")
                if key == "Method":
                    pdb_entry["method"] = val
                elif key == "Resolution":
                    pdb_entry["resolution"] = val
                elif key == "Chains":
                    pdb_entry["chains"] = val
            info["pdb_entries"].append(pdb_entry)
        elif db == "AlphaFoldDB":
            info["alphafold_id"] = xref.get("id", "")

    # MD-relevant summary
    info["md_notes"] = []
    if info["disulfide_bonds"]:
        info["md_notes"].append(f"{len(info['disulfide_bonds'])} disulfide bond(s) — use CYX in tLEaP")
    if info["ptm"]:
        info["md_notes"].append(f"{len(info['ptm'])} PTM(s) — may need custom parameters")
    if info["transmembrane"]:
        info["md_notes"].append(f"{len(info['transmembrane'])} TM region(s) — membrane simulation needed")
    if info["signal_peptide"]:
        sp = info["signal_peptide"]
        info["md_notes"].append(f"Signal peptide {sp['start']}-{sp['end']} — remove for mature protein")

    return info


@mcp.tool()
def get_variants(accession: str, disease_only: bool = False) -> dict:
    """Get known mutations/variants for a protein.
    Essential for wildtype vs mutant MD studies. Optional filter to disease-associated only.

    Essential for WT vs mutant MD comparison studies.
    Returns natural variants with disease associations and functional effects.
    """
    result = http_get(f"{UNIPROT_API}/uniprotkb/{accession}.json")
    if "error" in result:
        return result

    features = result.get("features", [])
    variants = []

    for feat in features:
        if feat.get("type") != "Natural variant":
            continue

        loc = feat.get("location", {})
        position = loc.get("start", {}).get("value")
        desc = feat.get("description", "")

        # Parse amino acid change
        alternativeSequence = feat.get("alternativeSequence", {})
        original = alternativeSequence.get("originalSequence", "")
        alt = alternativeSequence.get("alternativeSequences", [""])[0] if alternativeSequence.get("alternativeSequences") else ""

        # Check for disease association
        evidences = feat.get("evidences", [])
        ftId = feat.get("featureId", "")

        variant = {
            "position": position,
            "original": original,
            "variant": alt,
            "mutation": f"{original}{position}{alt}" if original and alt else desc,
            "description": desc,
            "id": ftId,
        }

        # Disease association from description
        if "in " in desc.lower() or "associated" in desc.lower() or "dbSNP" in desc:
            variant["disease_associated"] = True
        else:
            variant["disease_associated"] = False

        if disease_only and not variant["disease_associated"]:
            continue

        variants.append(variant)

    return {
        "accession": accession,
        "total_variants": len(variants),
        "variants": variants
    }


@mcp.tool()
def get_domains(accession: str) -> dict:
    """Get domain architecture: domain boundaries, active sites, binding sites, motifs.
    Helps decide which region to simulate + define analysis masks.

    Helps agent decide which region to simulate:
    - Domain boundaries for fragment simulations
    - Active site residues for analysis masks
    - Binding site residues for ligand interaction analysis
    """
    result = http_get(f"{UNIPROT_API}/uniprotkb/{accession}.json")
    if "error" in result:
        return result

    features = result.get("features", [])
    domains = {
        "domains": [],
        "regions": [],
        "active_sites": [],
        "binding_sites": [],
        "motifs": [],
    }

    for feat in features:
        ftype = feat.get("type", "")
        loc = feat.get("location", {})
        entry = {
            "type": ftype,
            "start": loc.get("start", {}).get("value"),
            "end": loc.get("end", {}).get("value"),
            "description": feat.get("description", ""),
        }

        if ftype == "Domain":
            domains["domains"].append(entry)
        elif ftype == "Region":
            domains["regions"].append(entry)
        elif ftype == "Active site":
            domains["active_sites"].append(entry)
        elif ftype == "Binding site":
            domains["binding_sites"].append(entry)
        elif ftype == "Motif":
            domains["motifs"].append(entry)

    return {"accession": accession, **domains}


@mcp.tool()
def map_pdb_residues(accession: str, pdb_id: str) -> dict:
    """Map residue numbers between UniProt and PDB.
    Critical when translating mutation positions to PDB coords.

    Critical for translating mutation positions (UniProt numbering)
    to PDB residue numbers (which may differ due to missing residues,
    expression tags, etc.)
    """
    # Use SIFTS mapping via PDBe
    url = f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{pdb_id.lower()}"
    result = http_get(url)

    if "error" in result:
        return result

    mappings = []
    pdb_data = result.get(pdb_id.lower(), {})
    uniprot_data = pdb_data.get("UniProt", {})
    acc_data = uniprot_data.get(accession, {})

    for mapping in acc_data.get("mappings", []):
        mappings.append({
            "chain": mapping.get("chain_id", ""),
            "uniprot_start": mapping.get("unp_start"),
            "uniprot_end": mapping.get("unp_end"),
            "pdb_start": mapping.get("start", {}).get("residue_number"),
            "pdb_end": mapping.get("end", {}).get("residue_number"),
        })

    return {
        "accession": accession,
        "pdb_id": pdb_id,
        "mappings": mappings
    }


if __name__ == "__main__":
    if "--test" in sys.argv:
        logger.debug("=== Search: EGFR human ===")
        logger.debug(json.dumps(search_protein("EGFR", organism="Homo sapiens", max_results=3), indent=2))
        logger.debug("\n=== Protein Info: P00533 (EGFR) ===")
        info = get_protein_info("P00533")
        info_short = {k: v for k, v in info.items() if k != "sequence"}
        info_short["sequence_length"] = len(info.get("sequence", ""))
        logger.debug(json.dumps(info_short, indent=2))
        logger.debug("\n=== Variants: P00533 (disease only) ===")
        logger.debug(json.dumps(get_variants("P00533", disease_only=True), indent=2))
    mcp.run()

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
from typing import Optional

from fastmcp import FastMCP
from _common import http_get, error_response, get_logger

mcp = FastMCP("chembl-server")
logger = get_logger(__name__)

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"


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


def _resolve_chembl_id(compound: str) -> dict:
    """Resolve compound name to ChEMBL ID + metadata.

    Returns dict with 'chembl_id' and 'pref_name' on success,
    or error_response dict on failure.
    """
    encoded = urllib.parse.quote(compound)
    # Preferred name search first
    url = f"{CHEMBL_API}/molecule.json?pref_name__icontains={encoded}&limit=5"
    result = http_get(url, timeout=45, retries=2)
    molecules = result.get("molecules", []) if "error" not in result else []

    if not molecules:
        # Fallback: synonym search via full-text endpoint
        url2 = f"{CHEMBL_API}/molecule/search.json?q={encoded}&limit=5"
        result2 = http_get(url2, timeout=45, retries=2)
        if "error" not in result2:
            molecules = [m for m in result2.get("molecules", [])
                         if m.get("pref_name") or m.get("molecule_synonyms")]

    if not molecules:
        if "error" in result:
            return result
        return error_response("not_found", f"Compound not found: {compound}")

    m = molecules[0]
    if len(molecules) > 1:
        names = [r.get('pref_name', r.get('molecule_chembl_id', 'unknown')) for r in molecules[:3]]
        logger.debug(f"Compound '{compound}' matched {len(molecules)} entries: {names}. Using first.")

    return {
        "chembl_id": m.get("molecule_chembl_id"),
        "pref_name": m.get("pref_name"),
    }


# ─── Tool Implementations ────────────────────────────────────────────────────

@mcp.tool()
def compound_search(name: str, max_results: int = 5) -> dict:
    """Search ChEMBL for compounds by name.
    Returns ChEMBL ID, SMILES, MW, charge, approval phase.

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
    result = http_get(url, timeout=45, retries=2)
    molecules = result.get("molecules", []) if "error" not in result else []

    if not molecules:
        # Fallback: synonym search via full-text endpoint
        url2 = f"{CHEMBL_API}/molecule/search.json?q={encoded}&limit={max_results}"
        result2 = http_get(url2, timeout=45, retries=2)
        if "error" not in result2:
            # Filter to entries that have a pref_name or synonym
            molecules = [m for m in result2.get("molecules", [])
                         if m.get("pref_name") or m.get("molecule_synonyms")]
        elif "error" in result2:
            # M-53: surface second-API error so failures don't get silently swallowed
            if "error" in result:
                return {"query": name, "error": "both_apis_failed",
                        "primary_error": result.get("error"),
                        "fallback_error": result2.get("error")}

    if not molecules and "error" in result:
        return result
    if not molecules:
        return {"query": name, "results": [], "message": "No compounds found in ChEMBL"}

    compounds = [_format_molecule(m) for m in molecules[:max_results]]

    if len(molecules) > 1:
        names = [r.get('pref_name', r.get('molecule_chembl_id', 'unknown')) for r in molecules[:3]]
        logger.debug(f"Compound '{name}' matched {len(molecules)} entries: {names}. Using first match.")

    return {"query": name, "results": compounds, "n_results": len(compounds)}


@mcp.tool()
def get_bioactivity(compound: str, target: Optional[str] = None, activity_type: Optional[str] = None, max_results: int = 20) -> dict:
    """Curated bioactivity (Ki/IC50/EC50) from ChEMBL.
    PRIMARY tool for validating MD-computed ΔG. Auto-converts Ki(nM) → ΔG(kcal/mol).

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
        resolved = _resolve_chembl_id(compound)
        if "error" in resolved:
            return resolved
        chembl_id = resolved["chembl_id"]
        compound_name = resolved["pref_name"]
    else:
        compound_name = compound

    # Filter to activities with pChEMBL values (curated, unit-normalised) and sort
    # by pChEMBL descending so the top-N are always the most potent/reliable hits
    params = f"molecule_chembl_id={chembl_id}&pchembl_value__isnull=false&order_by=-pchembl_value&limit={max_results}"
    if activity_type:
        params += f"&standard_type={urllib.parse.quote(activity_type)}"
    url = f"{CHEMBL_API}/activity.json?{params}"
    result = http_get(url, timeout=45, retries=2)

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
            "dg_kcal_mol is computed as RT·ln(Ki_M) at 300 K (matches MD simulation temperature) — negative means favourable binding. "
            "PMF from umbrella sampling is positive (work to unbind). Sign convention: ΔG_bind = -PMF_unbind."
        ),
    }


@mcp.tool()
def target_search(name: str, organism: str = "Homo sapiens", max_results: int = 5) -> dict:
    """Search ChEMBL for biological targets.
    Returns target ChEMBL IDs + classifications.

    Returns ChEMBL target IDs and classifications. The target_chembl_id
    can be used with get_bioactivity() to find all actives against a target.

    Args:
        name: Target protein name or gene symbol (e.g., "HIV-1 protease", "EGFR")
        organism: Filter by organism (default: "Homo sapiens")
        max_results: Number of results (default: 5)
    """
    encoded = urllib.parse.quote(name)
    url = f"{CHEMBL_API}/target.json?pref_name__icontains={encoded}&limit={max_results}"
    result = http_get(url, timeout=45, retries=2)

    if "error" in result:
        return result

    targets_raw = result.get("targets", [])
    targets = []
    for t in targets_raw:
        org = t.get("organism", "") or ""
        if organism and organism.lower() not in org.lower():
            # H-19 fix: the original logic was inverted — it excluded human targets when
            # searching for non-human organisms. Corrected: skip entries where the
            # requested organism string is not in the target's organism field.
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


@mcp.tool()
def get_mechanism(drug: str) -> dict:
    """Mechanism of action for an approved drug.
    Returns binding mechanism, action type, primary target.

    Returns binding mechanism, action type, and the primary target.
    Useful for understanding pharmacology before setting up MD.

    Args:
        drug: Drug name (e.g., "ritonavir") or ChEMBL ID
    """
    # Resolve to ChEMBL ID
    chembl_id = drug
    compound_name = drug
    if not drug.upper().startswith("CHEMBL"):
        resolved = _resolve_chembl_id(drug)
        if "error" in resolved:
            return resolved
        chembl_id = resolved["chembl_id"]
        compound_name = resolved["pref_name"]

    url = f"{CHEMBL_API}/mechanism.json?molecule_chembl_id={chembl_id}&limit=20"
    result = http_get(url, timeout=45, retries=2)

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


@mcp.tool()
def drug_search(indication: str, max_results: int = 10) -> dict:
    """Find approved drugs by therapeutic indication.
    Searches drug indication (clinical trial + approval data).

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
    result = http_get(url, timeout=45, retries=2)

    indications = result.get("drug_indications", []) if "error" not in result else []

    if not indications:
        url2 = (f"{CHEMBL_API}/drug_indication.json"
                f"?mesh_heading__icontains={encoded}&max_phase_for_ind__gte=3&limit={max_results}")
        result2 = http_get(url2, timeout=45, retries=2)
        # M-53: surface both-API failure
        if "error" in result and "error" in result2:
            return {"indication": indication, "error": "both_apis_failed",
                    "primary_error": result.get("error"),
                    "fallback_error": result2.get("error")}
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


@mcp.tool()
def get_admet(compound: str) -> dict:
    """ADMET / drug-likeness for a compound.
    Lipinski Ro5, AlogP, PSA, QED, formal charge, flexibility.

    Returns Lipinski Ro5 descriptors, AlogP, PSA, QED score, and
    predicted CYP inhibition (where available). Use to assess
    whether a ligand is suitable for MD binding studies.

    Args:
        compound: ChEMBL ID (e.g., "CHEMBL163") or compound name
    """
    chembl_id = compound
    compound_name = compound
    if not compound.upper().startswith("CHEMBL"):
        resolved = _resolve_chembl_id(compound)
        if "error" in resolved:
            return resolved
        chembl_id = resolved["chembl_id"]
        compound_name = resolved["pref_name"]

    url = f"{CHEMBL_API}/molecule/{chembl_id}.json"
    result = http_get(url, timeout=45, retries=2)

    if "error" in result:
        return result

    props = result.get("molecule_properties") or {}
    struct = result.get("molecule_structures") or {}

    # H-20 fix: wrap full_mwt conversion in try/except (malformed API string would crash)
    try:
        mw = float(props.get("full_mwt") or 0)
    except (ValueError, TypeError):
        mw = 0.0
    hba = int(props.get("hba") or 0)
    hbd = int(props.get("hbd") or 0)
    ro5_violations = int(props.get("num_ro5_violations") or 0)
    # H-21 fix: same for alogp
    try:
        alogp = float(props.get("alogp") or 0)
    except (ValueError, TypeError):
        alogp = 0.0

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


if __name__ == "__main__":
    if "--test" in sys.argv:
        logger.debug("=== compound_search: ritonavir ===")
        r = compound_search("ritonavir", max_results=2)
        logger.debug(json.dumps(r, indent=2))

        chembl_id = (r.get("results") or [{}])[0].get("chembl_id", "CHEMBL163")
        logger.debug(f"=== get_bioactivity: {chembl_id} vs HIV protease ===")
        logger.debug(json.dumps(get_bioactivity(chembl_id, target="HIV", activity_type="Ki", max_results=5), indent=2))

        logger.debug(f"=== get_mechanism: ritonavir ===")
        logger.debug(json.dumps(get_mechanism("ritonavir"), indent=2))

        logger.debug(f"=== get_admet: ritonavir ===")
        logger.debug(json.dumps(get_admet("ritonavir"), indent=2))

        logger.debug(f"=== drug_search: HIV ===")
        logger.debug(json.dumps(drug_search("HIV", max_results=5), indent=2))
    else:
        mcp.run()

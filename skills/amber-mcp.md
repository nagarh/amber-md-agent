# Skill: amber-mcp

MCP server integration guide. Read before fetching structures, parametrizing ligands, planning protocols, or validating free energy results.

## Critical: Call via Python import, NOT MCP tool calls

MCP protocol hangs on this cluster. All 7 servers are local Python files in `mcp_servers/`.

```python
import sys; sys.path.insert(0, 'mcp_servers/')
from pubchem_server import search_compound, get_3d_conformer
from pdb_server import get_validation_report, search_pdb
from uniprot_server import get_protein_info, map_pdb_residues, get_variants
from alphafold_server import get_prediction, get_plddt_scores, get_pae
from chembl_server import get_bioactivity
from stringdb_server import get_interaction_partners, get_network, get_functional_enrichment
from pubmed_server import search_literature, search_protocol, compare_to_literature, format_citation
```

Or run via CLI (works for all servers):
```bash
python mcp_servers/pubmed_server.py search_protocol '{"system_keywords":"X", "n":10}'
```

## Mandatory (always run these)

| Step | Call | Why |
|------|------|-----|
| Before accepting any structure | `pdb.get_validation_report(pdb_id)` | Catches bad resolution, clashscore, missing residues — corrupt structure wastes 168h GPU job |
| Before antechamber | `pubchem.search_compound(name)` | Gets formal charge for `-nc` flag — wrong charge is silent fatal error |
| Ligand parametrization | `pubchem.get_3d_conformer(cid, path)` | Only reliable source of correct H count + connectivity |
| Step 2 (planning) | `pubmed.search_protocol(system, sim_type, n=10)` | Ground sim length / FF / observables in published practice |
| Step 7 (results) | `pubmed.compare_to_literature(observable, system, n=5)` | Real DOIs for STUDY_REPORT §9 — no training-memory guesses |
| After TI/MM-GBSA results | `chembl.get_bioactivity(compound, target)` | Validate computed ΔG against experiment — scientific closure |

## Conditional (only if not already known)

| Situation | Call |
|-----------|------|
| No PDB ID provided | `pdb.search_pdb(query, organism, resolution_max)` |
| Unfamiliar protein — PTMs, disulfides, domain boundaries | `uniprot.get_protein_info(accession)` |
| PDB residue numbering mismatch suspected | `uniprot.map_pdb_residues(accession, pdb_id)` |
| Studying a mutation | `uniprot.get_variants(accession)` |
| No crystal structure at adequate resolution | `alphafold.get_prediction(uniprot_id)` → `get_plddt_scores` |
| Multi-domain protein, arrangement uncertain | `alphafold.get_pae(uniprot_id)` |
| Multi-protein or allosteric simulation | `stringdb.get_interaction_partners` / `get_network` |
| Post-simulation pathway interpretation | `stringdb.get_functional_enrichment` |

## Structure Selection Loop

When no PDB ID given, iterate — do NOT just take first result:

```python
import sys; sys.path.insert(0, 'mcp_servers/')
from pdb_server import search_pdb, get_validation_report

results = search_pdb(query, organism, resolution_max=3.0)
# results already sorted by resolution (low Å first)

selected = None
for pdb_id in results:
    python md_agent.py fetch pdb_id        # download
    result = python md_agent.py preflight <pdb_id>.pdb  # check breaks
    if "chain break" not in preflight result:
        report = get_validation_report(pdb_id)
        if report["resolution"] < 2.5 and report["clashscore"] < 20 and report["ramachandran_outliers"] < 2:
            selected = pdb_id
            break
        # else: quality fail → try next intact structure

# All intact structures failed quality gate
if not selected:
    selected = highest_resolution_intact  # pick best no-break structure
    # STOP: warn user — quality issues, offer: proceed or provide PDB

# All structures have chain breaks
if all_have_breaks:
    selected = minimum_breaks_structure  # fewest missing residues
    → invoke loop modeling (scripts/loop_model.py)
```

## Skip when

- User gave PDB ID → just `python md_agent.py fetch <PDB_ID>`, skip search
- Crystal structure exists at good resolution → skip AlphaFold entirely
- Single-protein binding study → skip stringdb entirely
- Not planning FEP series → skip `pubchem.get_similar_compounds`
- Not doing ADMET analysis → skip `chembl.drug_search`, `get_mechanism`, `get_admet`
- Server is down → fall back gracefully, inform user, continue with what's available

## PDB Validation Report — What to Check

```python
report = pdb.get_validation_report(pdb_id)
# Check:
# - resolution < 2.5 Å (prefer < 2.0 Å)
# - clashscore < 20 (prefer < 10)
# - missing residues near binding site → potential issue
# - Ramachandran outliers < 2%
```
Bad structure = wasted GPU hours. Validate before any system build.

# MCP Integration Architecture for AmberMD Agent

## What MCP Gives Us

Without MCP, the agent is a local tool — it can only use what's installed on the machine.
With MCP, the agent becomes a **networked computational chemist** that queries live science
databases in real-time, finds structures automatically, and validates computed results against
experimental data.

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Claude Code (the brain)                          │
│                                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Amber    │  │ RAG      │  │ ChEMBL   │  │ PDB      │             │
│  │ Toolkit  │  │ (Manual) │  │ (local)  │  │ (local)  │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │              │             │              │                    │
│  ┌────┴─────┐  ┌─────┴─────┐  ┌───┴──────┐  ┌───┴──────┐            │
│  │ SLURM    │  │ UniProt   │  │ PubChem  │  │ AlphaFold│            │
│  │ Cluster  │  │ (local)   │  │ (local)  │  │ (local)  │            │
│  └────┬─────┘  └─────┬─────┘  └───┬──────┘  └───┬──────┘            │
│       │              │             │              │                    │
│  ┌────┴──────────────┴─────────────┴──────────────┴──────────────┐   │
│  │                   STRING-DB (local)                             │   │
│  │          PPI networks · pathway enrichment · off-targets        │   │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    Agent Decision Layer                          │  │
│  │  "User wants binding FE of compound X to protein Y"              │  │
│  │   1. PDB → find best structure, check validation report          │  │
│  │   2. UniProt → domain boundaries, disease mutations              │  │
│  │   3. PubChem → SMILES + 3D conformer for antechamber             │  │
│  │   4. ChEMBL → experimental Ki to validate ΔG against             │  │
│  │   5. RAG → read TI/FEP protocol from Amber manual                │  │
│  │   6. Toolkit + SLURM → build system, run, analyze                │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Live MCP Servers (Available Now)

### 1. ChEMBL — Drug & Bioactivity Database
**Type**: Local server (`mcp_servers/chembl_server.py`)
**Config**: `.mcp.json` → `"chembl"`

Tools:
- `compound_search(name)` → SMILES, MW, logP, ChEMBL ID
- `get_bioactivity(compound, target)` → experimental IC50/Ki/EC50 with assay details
- `drug_search(indication)` → approved drugs for a disease
- `get_mechanism(drug)` → binding mechanism, primary target
- `get_admet(compound)` → drug-likeness, permeability, solubility
- `target_search(protein)` → compounds that hit a protein target

**Key use**: Get experimental binding data to validate computed ΔG. If computed Ki matches ChEMBL Ki, the simulation is validated.

---

### 2. PDB — RCSB Protein Data Bank
**Type**: Local server (`mcp_servers/pdb_server.py`)
**Config**: `.mcp.json` → `"pdb"`

Tools:
- `search_pdb(query, organism, resolution_max)` → ranked structures with metadata
- `get_structure_info(pdb_id)` → chains, ligands, resolution, R-free, organism
- `get_ligand_info(pdb_id, ligand_code)` → SMILES, formula, binding site residues
- `get_validation_report(pdb_id)` → clashscore, Ramachandran, rotamer outliers, R-free
- `find_similar_structures(pdb_id)` → homologs, alternate crystal forms

**Key use**: Always call `get_validation_report` before using a structure for MD — a poor-quality structure will cause artefacts regardless of simulation settings.

---

### 3. UniProt — Protein Knowledge Base
**Type**: Local server (`mcp_servers/uniprot_server.py`)
**Config**: `.mcp.json` → `"uniprot"`

Tools:
- `search_protein(name, organism)` → UniProt accession and summary
- `get_protein_info(accession)` → function, sequence, domains, PTMs, disulfides, TM regions
- `get_variants(accession)` → disease-associated mutations (for WT vs mutant studies)
- `get_domains(accession)` → domain boundaries, active sites, binding sites
- `map_pdb_residues(accession, pdb_id)` → UniProt ↔ PDB residue number mapping

**Key use**: Before capping termini, get the true domain boundaries from UniProt so you know whether the PDB represents a truncated construct (needs ACE/NME caps) or full-length protein.

---

### 4. PubChem — Small Molecule Database
**Type**: Local server (`mcp_servers/pubchem_server.py`)
**Config**: `.mcp.json` → `"pubchem"`

Tools:
- `search_compound(name)` → CID, SMILES, formal charge, LogP, MW
- `get_compound_properties(cid)` → full properties + MD-specific notes (protonation state, charge)
- `get_3d_conformer(cid, output_path)` → download SDF for antechamber input
- `get_bioassay_summary(cid, target)` → experimental activity
- `get_similar_compounds(cid)` → analogs for FEP congeneric series

**Key use**: `get_3d_conformer` downloads the 3D SDF file directly — feed it straight to antechamber for GAFF2 parametrization without the user needing to draw or find the structure.

---

### 5. AlphaFold — Predicted Structure Database
**Type**: Local server (`mcp_servers/alphafold_server.py`)
**Config**: `.mcp.json` → `"alphafold"`

Tools:
- `get_prediction(uniprot_id)` → pLDDT confidence scores, PAE, MD suitability assessment
- `download_structure(uniprot_id, output_path)` → PDB file with pLDDT in B-factors
- `get_plddt_scores(uniprot_id)` → per-residue confidence + restraint suggestions
- `get_pae(uniprot_id)` → domain interaction reliability (PAE matrix)

**Key use**: When no experimental structure exists. Regions with pLDDT < 70 are disordered — apply positional restraints or truncate. PAE matrix reveals which domain pairs are reliably predicted.

---

### 6. STRING-DB — Protein Interaction Networks
**Type**: Local server (`mcp_servers/stringdb_server.py`)
**Config**: `.mcp.json` → `"stringdb"`

Tools:
- `get_interaction_partners(protein, organism, limit, score_threshold)` → experimentally validated interactors with evidence scores
- `get_network(proteins, organism, score_threshold)` → full PPI network for a set of proteins
- `get_functional_enrichment(proteins, organism)` → GO terms, KEGG pathways, Reactome pathways
- `map_protein_ids(proteins, organism)` → verify STRING recognizes your protein names

**Key use**: Before planning a simulation, understand who your target talks to — high-confidence experimental partners (escore > 0.7) are candidates for protein-protein interface simulations. Pathway enrichment contextualizes MD results biologically.

---

## Current `.mcp.json`

```json
{
  "mcpServers": {
    "chembl": {
      "command": "python3",
      "args": ["mcp_servers/chembl_server.py"]
    },
    "pdb": {
      "command": "python3",
      "args": ["mcp_servers/pdb_server.py"]
    },
    "uniprot": {
      "command": "python3",
      "args": ["mcp_servers/uniprot_server.py"]
    },
    "pubchem": {
      "command": "python3",
      "args": ["mcp_servers/pubchem_server.py"]
    },
    "alphafold": {
      "command": "python3",
      "args": ["mcp_servers/alphafold_server.py"]
    },
    "stringdb": {
      "command": "python3",
      "args": ["mcp_servers/stringdb_server.py"]
    }
  }
}
```

---

## Decision Guide: Which Server for What

| Situation | Use |
|-----------|-----|
| User gives protein name, not PDB ID | UniProt → PDB search |
| Need to pick the best structure | PDB search + `get_validation_report` |
| No experimental structure exists | AlphaFold → check pLDDT |
| User gives drug/compound name, not SMILES | PubChem or ChEMBL search |
| Need ligand 3D coordinates | PubChem `get_3d_conformer` |
| Need to validate computed ΔG | ChEMBL `get_bioactivity` |
| User wants to study a mutation | UniProt `get_variants` → `map_pdb_residues` |
| Multi-domain protein, unsure of arrangement | AlphaFold `get_pae` |
| Protein has PTMs or disulfides | UniProt `get_protein_info` |
| Protein is truncated construct? | UniProt domains → determine if ACE/NME caps needed |
| Need to know what interacts with the target | STRING-DB `get_interaction_partners` |
| Planning multi-protein or allosteric simulation | STRING-DB `get_network` |
| Want pathway context for MD results | STRING-DB `get_functional_enrichment` |

---

## Example: Complete Research Workflow

```
User: "Study how the L858R mutation affects erlotinib binding to EGFR"

Step 1 — Understand the protein (UniProt):
  search_protein("EGFR", "Homo sapiens") → accession P00533
  get_protein_info("P00533")
    → kinase domain boundaries (residues 712–979), 4 disulfide bonds in ectodomain
  get_variants("P00533")
    → L858R confirmed lung cancer driver mutation

Step 2 — Find structures (PDB):
  search_pdb("EGFR erlotinib", resolution_max=2.5)
    → 1M17 (WT + erlotinib, 2.6 Å)
  get_validation_report("1M17")
    → clashscore 8.2, Ramachandran 96.1% — acceptable for MD
  search_pdb("EGFR L858R erlotinib")
    → 2ITZ (mutant, 2.4 Å)

Step 3 — Get compound data (PubChem + ChEMBL):
  search_compound("erlotinib") → CID 176870, formal charge 0
  get_3d_conformer(176870, "erlotinib.sdf") → ready for antechamber
  ChEMBL: get_bioactivity("erlotinib", "EGFR")
    → WT Ki = 2 nM, L858R Ki = 40 nM → ΔΔG target = +1.8 kcal/mol

Step 4 — Biological context (STRING-DB):
  get_interaction_partners("EGFR")
    → ERBB2, KRAS, SRC are high-confidence interactors
    → Note: consider allosteric effects from ERBB2 heterodimerization

Step 5 — Protocol from manual (RAG):
  rag-query "thermodynamic integration protein mutation"
  rag-query "free energy perturbation alchemical"
  → Read TI setup: 11 lambda windows, ifsc=1, ntmin=2 required

Step 6 — Execute (Toolkit + SLURM):
  cap_protein.py → ACE/NME caps on kinase domain construct
  tLEaP → build WT and L858R systems
  write-slurm-array → submit TI windows (uses slurm_template.sh)
  analyze → integrate dV/dλ across windows

Step 7 — Validate:
  ΔΔG_computed = +1.8 kcal/mol vs ΔΔG_experimental = +1.8 kcal/mol ✓
  L858R weakens erlotinib binding by ~20-fold — consistent with clinical resistance data
```

---

## Impact: Without vs With MCP

| Capability | Without MCP | With MCP |
|------------|-------------|----------|
| Ligand setup | User must provide SMILES | Auto-lookup from PubChem/ChEMBL |
| 3D ligand structure | User must draw or find it | PubChem `get_3d_conformer` → antechamber |
| Experimental validation | None | Compare ΔG with measured Ki/IC50 from ChEMBL |
| Protein context | Just PDB coordinates | Full UniProt annotation, domains, PTMs |
| Structure selection | User picks PDB ID | Agent searches, evaluates quality, picks best |
| Missing structures | Ask user | AlphaFold predicted structure with confidence map |
| Off-target context | None | STRING-DB PPI network |
| Mutation studies | User specifies residue manually | UniProt variants → disease mutations list |
| Pathway interpretation | None | STRING-DB pathway enrichment |
| Truncated constructs | Often missed, causes artefacts | UniProt domain boundaries → auto cap decision |

---

## Potential Future Integrations

### BindingDB
- Experimental binding data for thousands of protein-ligand pairs
- Cross-validate FE results against measured Kd/Ki/IC50

### PubMed / Literature Search
- Find published simulation protocols for specific protein families
- Extract force field choices, water models, simulation lengths from methods sections

### Simulation Database (local)
- Store and retrieve past simulation results
- "Have I simulated this protein before? What parameters worked?"
- Track convergence history, force field choices, computed ΔG values

### Molecular Viewer MCP
- Render structures and trajectories directly in the chat
- Highlight binding sites, mutations, key interaction residues

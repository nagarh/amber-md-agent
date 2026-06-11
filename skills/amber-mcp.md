# Skill: amber-mcp

MCP server integration guide. Read before fetching structures, parametrizing ligands, planning protocols, or validating free energy results.

## Critical: MCP-only

All 8 servers (amber + 7 domain servers) run as FastMCP servers registered in `.mcp.json`. Tools are exposed under the `mcp__<server>__<tool>` namespace and called directly by the agent. **Never** spawn `python` subprocesses (`python scripts/...`, `python mcp_servers/...`) — use the MCP tool of the same name instead. Python imports outside the agent loop (e.g. one-off scratch scripts) are unrelated.

```
mcp__amber__fetch_pdb(pdb_id="2HYY", output_dir="studies/<name>/raw_pdbs")
mcp__pubmed__search_protocol(system_keywords="X", n=10)
mcp__chembl__get_bioactivity(compound="ritonavir", target="HIV")
mcp__pdb__get_validation_report(pdb_id="2HYY")
mcp__alphafold__download_structure(uniprot_id="P00533", output_path="...")
```

Servers: `amber`, `pdb`, `pubchem`, `uniprot`, `alphafold`, `chembl`, `stringdb`, `pubmed` — all registered in `.mcp.json`. Verify with `claude mcp list`.

## Mandatory (always run these)

| Step | Call | Why |
|------|------|-----|
| Before accepting any structure | `mcp__pdb__get_validation_report(pdb_id)` | Catches bad resolution (>2.5 Å), clashscore (>20), Ramachandran outliers (>2%), missing-residue regions — corrupt structure wastes 168h GPU job. **Single source of truth for these gates = Structure Selection Loop step 2.iv (L52); keep both in sync.** Threshold provenance: clashscore and Ramachandran-outlier definitions follow MolProbity / wwPDB validation metrics (Williams et al. 2018, *Protein Sci* 27:293; wwPDB X-ray validation report). The specific cutoffs (2.5 Å, clashscore 20, 2% outliers) are heuristic accept guardrails, not fixed wwPDB standards — MolProbity reports clashscore and Ramachandran as resolution-binned percentiles, so these gates are ideally applied resolution-aware (a 2.8 Å structure with clashscore 20 may be a good percentile, while the same value at 1.5 Å is poor). |
| Before antechamber on a crystal ligand | `mcp__amber__build_ligand_from_crystal(resname, pdb_path, drug_name, out_sdf)` | One-call pipeline (CCD bond orders + PubChem cross-validate + MCS coord-transplant + AddHs); returns formal charge for `-nc` flag + H-count for validation |
| Step 2 (planning) | `mcp__pubmed__search_protocol(system, sim_type, n=10)` | Ground sim length / FF / observables in published practice |
| Step 7 (results) | `mcp__pubmed__compare_to_literature(observable, system, n=5)` | Real DOIs for STUDY_REPORT §9 — no training-memory guesses |
| After TI / MM-GBSA results | `mcp__chembl__get_bioactivity(compound, target)` | Validate computed ΔG against experiment — scientific closure |
| After propka3 SUMMARY parse | `mcp__amber__apply_protonation_overrides(...)` | Encodes the rename rules; never sed/inline `python -c` to rewrite residue names |

## Conditional (only if not already known)

| Situation | Call |
|-----------|------|
| No PDB ID provided | `mcp__pdb__search_pdb(query, organism, resolution_max)` |
| Unfamiliar protein — PTMs, disulfides, domain boundaries | `mcp__uniprot__get_protein_info(accession)` |
| PDB residue numbering mismatch suspected | `mcp__uniprot__map_pdb_residues(accession, pdb_id)` |
| Studying a mutation | `mcp__uniprot__get_variants(accession)` |
| No crystal structure at adequate resolution | `mcp__alphafold__get_prediction(uniprot_id)` → `get_plddt_scores` |
| Multi-domain protein, arrangement uncertain | `mcp__alphafold__get_pae(uniprot_id)` |
| Multi-protein or allosteric simulation | `mcp__stringdb__get_interaction_partners` / `get_network` |
| Post-simulation pathway interpretation | `mcp__stringdb__get_functional_enrichment` |

## Structure Selection Loop

When no PDB ID is given, iterate — do not just take the first result.

1. `mcp__pdb__search_pdb(query, organism, resolution_max=3.0)` — results are already ranked by resolution (low Å first). Note: `resolution_max=3.0` is a deliberately permissive *candidate net* (cast wide to gather options), not the accept gate — the actual selection bar is the stricter `resolution < 2.5` quality gate in step 2.iv. If no candidate passes the gate, widen `resolution_max` (e.g. 3.5) to surface more options before falling back to step 3's highest-resolution-intact warning path.
2. For each candidate `pdb_id`, in order:
   1. `mcp__amber__fetch_pdb(pdb_id, output_dir="studies/<name>/raw_pdbs")`
   2. `mcp__amber__preflight(pdb_file="studies/<name>/raw_pdbs/<pdb_id>.pdb")`
   3. If preflight reports chain breaks → skip to next candidate, keep this one in a "has-breaks" list.
   4. If no breaks → `mcp__pdb__get_validation_report(pdb_id)`. Pass criteria (single source of truth; the prose gate at L23 mirrors these): `resolution < 2.5` AND `clashscore < 20` AND `ramachandran_outliers < 2`. Pass → select this structure, stop loop. Fail → try next intact candidate. Provenance: clashscore / Ramachandran metrics per MolProbity / wwPDB validation (Williams et al. 2018, *Protein Sci* 27:293); the numeric cutoffs are heuristic accept guardrails, not absolute wwPDB pass marks — since MolProbity scores these as resolution-binned percentiles, prefer judging clashscore/Ramachandran resolution-aware where the report exposes percentiles.
3. If all intact candidates fail the quality gate → pick the highest-resolution intact one, STOP, warn the user, offer to proceed or accept a user-provided PDB.
4. If all candidates have breaks → pick the one with the fewest missing residues, then run `mcp__amber__loop_model(pdb, missing, uniprot, out, auto_low_confidence="prompt")` and respond to the pLDDT verdict with `accept` / `reject` / `cap` per the agent's reasoning. **MANDATORY post-graft**: call `mcp__amber__validate_loop_junction(pdb_file=out)` — silent geometry corruption is the BACE1-class bug (see Audit_3 C-01). Skip = study invalid.

   **Known loop_model bugs:**
   - **DBREF offset bug (FIXED)**: `loop_model.py` now reads DBREF records automatically and applies the correct UniProt offset for both pLDDT lookup and AF residue extraction. Previously caused pLDDT=null and 55+ Å junction failures for proteins with large DBREF offsets (e.g. 5YNP chain A offset=6775). No workaround needed — fix is in scripts/loop_model.py via `parse_dbref_offsets()`.
   - **Conformation mismatch**: AlphaFold models one conformational state (usually active/DFG-in). If the crystal is in a different state (DFG-out, open/closed loop, etc.), graft will fail with large junction distances. `validate_loop_junction` will catch this (FAIL). Correct action: use `action="cap"`, or find a template crystal in the same conformational state. Never force-accept a graft with junction > 0.5 Å. The 0.5 Å junction tolerance is a heuristic guardrail: a well-closed backbone graft should leave the bridging peptide bond near its ideal Cα–Cα / C–N geometry, so a junction deviation well under ~1 bond-length flags clean closure, whereas the BACE1-class failures showed tens of Å (see Audit_3 C-01). It is not a published Amber/MolProbity constant — tighten or loosen per CCD closure quality if a future case justifies it.

## Skip when

- User gave PDB ID → `mcp__amber__fetch_pdb(pdb_id=..., output_dir=...)`, skip search loop
- Crystal structure exists at good resolution → skip AlphaFold
- Single-protein binding study → skip stringdb
- Not planning FEP series → skip `mcp__pubchem__get_similar_compounds`
- Not doing ADMET analysis → skip `mcp__chembl__drug_search` / `get_mechanism` / `get_admet`
- Server is down → fall back gracefully, inform user, continue with what's available

Bad structure → wasted GPU hours. Validate before any system build.

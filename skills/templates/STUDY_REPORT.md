# Template: STUDY_REPORT.md

Written once after analysis complete (Step 7). Scientific report — objective, methods, RMSD/RMSF/ΔG results, key findings.

**Lock to this structure — do not freelance new sections.** Every section is required even if short. Quantitative claims must cite the file/line they came from.

---

```markdown
# Study Report — <descriptive title>
Date: <YYYY-MM-DD>

## 1. Objective
One paragraph. What biological/chemical question. Why this PDB. What you expect to learn.
Distinguish "stability check" vs "binding study" vs "rare-event sampling" — sets the bar for interpretation later.

## 2. System
- PDB: <ID>, <oligomeric state from REMARK 350>
- Chains kept / simulation construct: <which chains, why>
- Atom count: <N>
- Box: <model>, <padding> Å, <volume>
- Ligand (if any): <name, source, charge, parametrization route>
- Special features: <metals, cofactors, modified residues, disulfides, membrane>

## 3. Protonation Rationale
Required even if all standard. State the pH, then list non-default residues with explicit reasoning (pKa from manual / literature / electrostatic context).

| Residue | State | pKa context | Rationale |
|---------|-------|-------------|-----------|

## 4. Methods (mdin settings — quote ACTUAL values used in this study)
This table is filled with the actual values from the executed mdin files — NOT a template. Read each mdin, copy verbatim. NO hardcoded examples below.

| Step | Ensemble | Thermostat | Barostat | dt | cut | SHAKE | Restraints | Length |
|------|----------|------------|----------|----|----|-------|------------|--------|
| Min1 | — | — | — | — | <Å> | — | <K> kcal/mol·Å² <mask> | <cyc> |
| Min2 | — | — | — | — | <Å> | — | <K> kcal/mol·Å² <mask> or none | <cyc> |
| Heat | <NVT/NPT> | <type γ=X> | <type taup=X or —> | <fs> | <Å> | <H/all> | <K> kcal/mol·Å² | <ps>, <T_init>→<T_final> K |
| Burst | <NVT/NPT> | <type γ=X> | <type taup=X> | <fs> | <Å> | <H/all> | <K> kcal/mol·Å² or none | <N> × <ps> |
| Equil2 | <NVT/NPT> | <type γ=X> | <type taup=X> | <fs> | <Å> | <H/all> | <K> kcal/mol·Å² | <ps> |
| Prod | <NVT/NPT> | <type γ=X> | <type taup=X or —> | <fs> | <Å> | <H/all> | <K> kcal/mol·Å² or none | <ns> |

## 5. Results
Quantitative — every value here cites a file path. No prose-only claims.

| Observable | Mean ± std | Range | Source |
|------------|------------|-------|--------|
| Backbone RMSD | X ± X Å | min–max | analysis/rmsd_backbone.dat |
| RMSF (overall) | X Å | max=X Å at res N | analysis/rmsf.dat |
| <study-specific, e.g. flap_tip distance> | X ± X Å | | analysis/<file>.dat |
| Density | X ± X g/cc | | prod.mdout AVERAGES |
| Temperature | X ± X K | | prod.mdout AVERAGES |
| Energy (Etot) | X ± X kcal/mol | | prod.mdout AVERAGES |

If plots generated → list paths.

## 6. Convergence Assessment
| Observable | drift_abs | threshold | status |
|------------|-----------|-----------|--------|
| Backbone RMSD | X Å | <drift_threshold> Å | converged / not_converged |

Justify `<drift_threshold>` per the 4-tier protocol (lit precedent → manual → training-knowledge, then manual validation) — do not hardcode a blanket cutoff; convergence criteria are system- and timescale-dependent. (A ~0.5 Å backbone-RMSD drift is a common heuristic guardrail, but cite the value you actually use.)

If any "not_converged" → say what was done about it: extend, accept with caveat, etc.

## 7. Key Findings
2–4 bullets, scientific conclusions only. Each bullet cites a row from §5.
Example: "Imatinib remains in ATP-pocket (ligand RMSD 1.6 Å throughout, §5)"
NOT: "the simulation went well" or "everything looks stable".

## 8. Caveats & Limitations
Required. What this study CANNOT conclude. Be specific:
- Simulation length vs required timescale ("1 ns < flap opening 10–100 ns")
- Force field limitations relevant to this system (ff14SB on IDP, GAFF2 for halogen bonds, etc.)
- Sampling: single replicate, no enhanced sampling, no replica exchange
- Starting structure bias: crystal vs solution state, crystal contacts, missing loops
- Temperature/density anomalies if present

## 9. Comparison to Literature
**Required: actually search pubmed_server, do not cite from memory.**

For each key observable in §5, run:
```
mcp__pubmed__compare_to_literature(
  observable_keyword="<obs>",
  system_keyword="<system>",
  n=5,
)
```

Then fill:
| Our value | Published value | Source (PMID:..., DOI:...) | Agreement |
|-----------|-----------------|----------------------------|-----------|
| flap_tip 5.6 Å | 5.3 ± 0.4 Å closed state | <Author Year, PMID:..., DOI:...> | ✓ |

If no relevant paper found for an observable → "No directly comparable published value" — DO NOT fabricate a citation.

## 10. Data Files
- Trajectory: simulations/prod/prod.nc (<N> frames, <interval> ps)
- Stripped trajectory: analysis/prod_stripped.nc
- Analysis: analysis/*.dat (list each)
- Reports: PROCESS_REPORT.md (engineering log)
- Approved plan: PLAN.md

## 11. References

### Method references (canonical, agent-confident)
This is a citation MENU, not a list of recommended defaults — cite ONLY the methods actually used in this study (per the FF/water/ion choices justified in PLAN.md via the 4-tier protocol). Delete rows for methods not used; add canonical refs for any method used but not listed here.
- ff14SB: Maier et al. 2015. PMID:26574453
- TIP3P: Jorgensen 1983. doi:10.1063/1.445869
- GAFF2 / antechamber: Wang 2004. PMID:15116359
- Joung-Cheatham ions: Joung & Cheatham 2008. PMID:18593145
- Amber manual: section/page numbers consulted (cite Step 2a queries)

### System-specific literature (from pubmed_server search)
Every entry MUST be a real PMID/DOI returned by `mcp__pubmed__search_literature` or `mcp__pubmed__compare_to_literature`. Use:
```
mcp__pubmed__format_citation(record=<record-from-search>, style="amber-report")
```
to format. **Never** cite from training memory — `[CHECK: training-memory]` is not acceptable; either search and cite, or omit.
```

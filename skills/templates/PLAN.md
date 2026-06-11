# Template: PLAN.md

Written at end of Step 4 (workflow), BEFORE any sbatch.
User must type `approve` (or `override X: Y`) before Step 5 begins.

**No hardcoded defaults.** Every parameter cell below must be filled per study using the 3-tier protocol:
1. **Tier 1 — Lit precedent** from Step 2b/2c pubmed search.
2. **Tier 2 — Amber 24 manual recommendation** via `rag_query` if Tier 1 empty.
3. **Tier 3 — Training knowledge** with explicit note "no lit, no manual rec, using <X> because <reason>" if both empty.
4. **Always — Manual validation** via `rag_query("leaprc.protein.<name>")` etc. to confirm the choice exists in Amber 24.

Banned phrases: `skill default`, `standard choice`, `<FF> by default`, copying parameters from a prior study without re-justifying.

---

```markdown
# Plan — <study_name>
Date: <YYYY-MM-DD>

## System (from preflight)
- PDB: <ID>, <oligomeric state>
- Biological unit: <from REMARK 350 check>
- Chains kept: <which chains>
- Atom count (estimated): <N>
- Special features: <truncated termini / disulfides / metals / cofactors / membrane / etc.>

## Force fields

### Selection protocol (per CLAUDE.md tier rule)

**Tier 1 — Lit precedent (from Step 2b/2c, primary source):**
For each precedent paper extract: protein FF, water model, ion model, reported accuracy vs experiment for the OBSERVABLE you need. If strong precedent exists for this observable + system class → candidate FF = that FF.

**Tier 2 — Amber 24 manual recommendation (if Tier 1 empty/weak):**
```
rag_query("force field recommendation <study type>")
rag_query("which protein force field <observable>")
rag_query("water model <ff candidate> compatibility")
```

**Tier 3 — Training knowledge (if Tiers 1+2 both empty):**
State explicitly: "No lit precedent. No manual recommendation. Using <X> based on training knowledge: <one-sentence reason>." User overrides at approval gate.

**ALWAYS — Manual validation (regardless of tier):**
```
rag_query("leaprc.protein.<name>")        # FF available
rag_query("leaprc.water.<name>")          # water available
rag_query("ions <water model> Joung-Cheatham OR Li-Merz")   # ion-water compat
```
Reject hallucinated FFs (e.g. "ff20SB" — not real) or incompatible pairings.

### FF table (REQUIRED format)

Every row cites BOTH lit precedent AND manual page. No row without both.

| Component | Choice | Lit precedent (PMID) | Manual page | Reason for this study |
|-----------|--------|---------------------|-------------|------------------------|
| Protein   | <name> | <PMID or "Tier 2/3: <reason>"> | Amber24 §X p.Y | <one sentence> |
| Water     | <name> | <PMID> | Amber24 §X p.Y | <one sentence> |
| Ions      | <scheme> | <PMID> | Amber24 §X p.Y | <one sentence> |
| Ligand    | <name> | <PMID or skill: amber-ligand.md> | Amber24 §X p.Y | <one sentence> |
| Metal ion | <ZAFF / 12-6-4 nonbonded / MCPB.py> | <PMID from Step 2c metal search> | Amber24 §3.7 p.55 or §14.2.2.6 p.286 | <coordination motif + why this model> |
(Omit metal row if no metal in system. Add rows for membrane/DNA/RNA/cofactor as needed.)

### Comparison-series studies
If this study compares to a prior study (same system, different mutation/ligand), FF must MATCH the prior study's FF (FF effects cancel only in matched series). Cite the prior study and re-validate FF against current manual.

## Protonation states
- pH chosen for this study: <X> (justify: biological compartment / experimental condition / lit precedent — NO default)
- propka3 run on starting structure: yes/no, log path

| Residue | State | Rationale |
|---------|-------|-----------|
| <residue ID> | <state code: ASH/GLH/HID/HIE/HIP/LYN/CYM> | <propka3 pKa + electrostatic context + buried/exposed status> |

Agent justifies pH choice itself in the section header — do not assume pH 7.
Cite literature + propka3 calculation supporting BOTH the pH choice AND each non-standard residue protonation state.

## Simulation Conditions (REQUIRED — surface explicitly so user can override)

| Condition | Value | Reason / source |
|-----------|-------|-----------------|
| Production temperature | <T> K | <biological context + lit PMID + manual page — NOT default 300 K> |
| Pressure | <P> atm | <NPT 1 atm standard for solution; 0 atm for vacuum; high-P studies override> |
| pH (links to §Protonation) | <X> | <see §Protonation rationale> |
| Ionic strength | <neutralize-only OR ~150 mM NaCl> | <see §Box ions> |

Common temperatures (pick + justify, NOT defaults):
- 277 K (4 °C, cryo); 290 K (X-ray); 298 K (NMR); 300 K (common MD); 310 K (human physiological);
- 313 K (fever); 323+ K (thermophile); 270–600 K (T-REMD ladder)

Selection criteria:
1. Biological active T (human → 310 K, thermophile → 333+ K)
2. Experimental reference structure T (NMR ~298, X-ray ~290)
3. Precedent paper T (Step 2b extraction)

## Simulation Protocol

Agent fills every cell per study from: (1) Amber 24 manual (RAG-cite section + page), (2) Lit precedent for THIS observable + system class (Step 2b PMID), (3) Training knowledge with explicit "Tier 3" note if neither.

Examples of when agent MUST override conventional values:
- Kinetics studies → lower γ_ln (e.g. 0.5 vs 2.0) to preserve dynamics
- Membrane systems → longer heating + Equil2, lipid21 thermostat handling
- IDP → longer prod + larger box than folded protein
- Free energy → matched timestep to softcore requirements (dt=0.001, ntc=1)
- Cold/high-T studies → water model + thermostat appropriate for T range

| Step | Setting | Time / cycles | Manual / lit source |
|------|---------|---------------|---------------------|
| Min1 | restrained backbone <K> kcal/mol·Å² | <N> cyc | <Amber24 §X p.Y> |
| Min2 | full | <N> cyc | <Amber24 §X p.Y> |
| Heat | NVT 0→<T> K, Langevin γ=<γ>, restrained <K> kcal/mol·Å² | <ps> | <Amber24 §X p.Y> |
| Burst density | NPT, barostat=<1 Berendsen | 2 MC>, taup=<τ>, no restraint | until mean <ρ>±<tol> g/cc + fluct < <f> | <Amber24 §X p.Y or skills/amber-bugs.md §burst> |
| Equil2 | NPT, barostat=1, taup=<τ>, restrained <K> kcal/mol·Å² | <N> ps | <Amber24 §X p.Y + Equil2 sizing reasoning below> |
| Production | NPT, MC barostat, no restraint | <N> ns | <user / lit PMID / manual + observable-timescale reasoning> |

### Production length + Equil2 sizing — agent picks per study

Reasoning chain required for BOTH (no default tables):

Production length:
1. Identify OBSERVABLE timescale from lit (Step 2b extraction): what ns/µs range did precedent papers use? Did they report convergence?
2. Estimate system-specific timescale (folding ~µs, binding ~10-100 ns, IDP > µs)
3. Apply user constraint (compute budget, walltime cap)
4. State chosen length in PLAN.md with: lit precedent PMID + observable timescale + caveat if shorter than precedent
5. If user gave length verbatim → use it, mark source `user prompt`

Equil2 sizing:
1. System size (tiny <15k, small <50k, medium <100k, large >100k, membrane — buckets are heuristic engineering guardrails, not from a cited source; refine per study)
2. Burst loop iterations needed before convergence
3. Density temperature recovery time (Langevin γ + system size)
4. Observable sensitivity to starting conformation (drug binding needs longer equil than stability check)

Auto-extend allowed if validate_step shows |T − target| > 5 K after equilibration (5 K is a heuristic engineering guardrail, not a cited threshold; tighten/loosen per study and note source) — log auto-extend in PROCESS_REPORT.md.

## Box
- Solvent model: <from §Force fields>
- Padding: <N> Å — agent picks per study. Reasoning:
  1. Minimum image convention vs. the chosen nonbonded cutoff (`cut`) — padding must exceed cut plus a conformational-drift buffer; cite the buffer choice to <Amber24 §X p.Y or lit PMID> for the chosen value
  2. System class drives a larger pad (IDP/extended states, allosteric loops, drug ligand binding where pocket conformations sample large volume) — justify the chosen padding against <Amber24 §X p.Y or lit PMID>, do not assume a fixed range
  3. Membrane systems: handled by packmol-memgen / CHARMM-GUI, NOT solvateBox
- Ions: from §Force fields (water-matched, validated)
  - Neutralization scheme — agent picks per study, justify in PLAN.md:
    - Neutralize-only (`addIons sys {ion} 0`): for free energy / binding studies where added salt alters the reference Hamiltonian
    - Physiological salt (~150 mM NaCl): neutralize first, then `addIons sys Na+ N Cl- N` for studies where ionic strength matters (electrostatics, IDPs, membrane potential, DNA/RNA)
  - Ion selection rule (Amber24 §13.6.5 p.249): run charge-check tLEaP (SLURM) before full tLEaP. Net charge < 0 → `addIons {unit} Na+ 0`. Net charge > 0 → `addIons {unit} Cl- 0`. Net charge = 0 → skip addIons. Count=0 means target net charge=0 (neutralize) — tLEaP adds however many ions needed. Not a count of 0. (Amber24 §13.6.5 p.249) NEVER specify both Na+ and Cl- when count=0.

## Analysis targets
- <observable-specific metrics from Step 2b lit + study objective, NO defaults>
- Agent picks based on what the study aims to characterize. Examples (NOT defaults): backbone RMSD, RMSF, secondary structure populations, distance/angle distributions, fraction native contacts, Rg, end-to-end distance, ΔG decomposition, etc.

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable / value |
|------------------------|--------|------------|-----|------------------------|
| <Author et al. Year, PMID:..., DOI:...> | <closest match> | <ns> | <ff> | <observed value> |
(3–5 most relevant papers. If 0 found → "no published precedent — agent decisions based on manual + training knowledge only, flagged for user review".)

Every parameter choice in this PLAN MUST be cross-referenced to:
- A lit row above (preferred), OR
- An Amber24 manual page (RAG-cited), OR
- An explicit "Tier 3: training knowledge — <reason>" note

## Method best practices (from Step 2c lit + RAG — MANDATORY if non-standard sim triggered)

Triggered by: <technique> (matched keyword: <keyword>)
(If Step 2c NOT triggered, write: "Standard MD — Step 2c skipped.")

| Paper (PMID, year) | Recommendation | Amber flag | Manual page | Adopted? |
|--------------------|----------------|------------|-------------|----------|
| <Author Year, PMID> | <text from abstract> | <gti_X=Y, etc.> | <page #> | ✓ or ✗ |

### Deviations from defaults (from Step 2c findings)

| Default value | New value | Reason (paper PMID + manual page) |
|---------------|-----------|-----------------------------------|
| scalpha=0.5 | scalpha=0.2 | Lee 2020 PMID:32672455 — default under gti_lam_sch=1 (manual p.513) |

If no deviations: write "No Step 2c deviations found — all method parameters justified per study via Tier 1/2 above."

## Walltime estimates
| System size | ns/day | This study walltime |
|-------------|--------|---------------------|
| <fill row matching atom count> | | min+heat ~30 min, equil2 ~30 min, prod ~<N> hr |

## Caveats / limitations
- <e.g. "1 ns insufficient for flap opening (10–100 ns regime)">
- <e.g. "Burst loop cools system — equil2 must warm back to target">
- <known cluster bugs that may surface>

## Approval: PENDING
```

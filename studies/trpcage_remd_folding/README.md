# README — trpcage_remd_folding

## Study
Trp-cage miniprotein (PDB 1L2Y, 20 residues) folding/unfolding thermodynamics by
temperature replica exchange MD (T-REMD), 16 replicas, 270–600 K, 100 ns/replica
(1.6 µs aggregate). Run date: 2026-05-17.

## Important — Force Field Caveat

**When this study was run, the agent was hardcoded to use ff14SB protein force
field + TIP3P water model.** This was a skill-level default baked into
`skills/amber-workflow.md` PLAN.md template (`| Protein | ff14SB | skill default |`)
and into `skills/amber-protein-prep.md` tleap example (`source leaprc.protein.ff14SB`,
`solvateBox sys TIP3PBOX 12.0`). The agent did not perform per-study force field
selection from literature or the Amber manual — it copy-pasted the default.

### Impact on this study's results

The ff14SB + TIP3P combination is well-known to over-stabilize folded states
for small proteins, particularly α-helical content. Direct consequences observed:

- **Computed Tm = 414 K (RMSD sigmoid) / 436 K (Cv peak)** vs experimental
  Tm ≈ 315 K (Neidigh 2002). Shift of ~100 K.
- Cold replicas (T < 400 K) trapped in folded basin — no unfolding events
  observed in 100 ns, P_fold = 1.000 even at 316 K (above experimental Tm).
- High-T replicas (> 460 K) sampled water above TIP3P boiling point (~410 K),
  producing unphysical structure-water energetics.

**The folding mechanism qualitatively correct (sharp two-state transition,
ΔH ≈ 12–15 kcal/mol consistent with English 2014 PMID:24448113), but the
temperature axis is shifted up by force-field bias.**

### Better force fields for this study (not used here)

| FF + water | Why better for folding Tm | Reference |
|------------|---------------------------|-----------|
| ff19SB + OPC | CMAP fixes helix over-stab; Tm within ~20 K of exp | Tian 2020, PMID:31894884 |
| ff15ipq + SPC/Eb | Self-consistent polarization; benchmarked on Trp-cage TC10b | Debiec 2016, PMID:27399642 |
| a99SB-disp + TIP4P-D | Folded+disordered both; best marginal-stability accuracy | Robustelli 2018, PMID:29735687 |
| AMBER99SB + TIP3P | Reproduced Tm=317 K vs exp 315 K (Trp-cage REMD) | English 2014, PMID:24448113 |

## Behavior fix (post-study)

After this study completed, the hardcoded force-field defaults were removed
from the agent's skills. The agent now selects protein FF + water model + ion
model **dynamically per study** using a 3-tier protocol:

1. **Tier 1 — Literature precedent:** Extract FF/water/ions used in the
   closest precedent papers (from Step 2b/2c PubMed search) for THIS
   observable + system class. Use full-text Methods section via
   `get_full_text(pmcid)` where available.
2. **Tier 2 — Amber 24 manual recommendation** (if Tier 1 empty): Query the
   manual via RAG for explicit FF recommendations by use case.
3. **Tier 3 — Training knowledge** (if Tiers 1+2 empty): Pick from training
   with explicit "no lit, no manual rec, using <X> because <reason>" note.
4. **Always — Manual validation:** Confirm chosen FF exists in Amber 24 via
   `rag_query("leaprc.protein.<name>")`. Catches hallucinated FFs and
   ion-water mismatches.

Every PLAN.md row for FF/water/ions now requires both a literature citation
(PMID) and a manual page reference. Banned phrases in PLAN.md: `skill default`,
`standard choice`, `<FF> by default`, or copying parameters from a prior study
without re-justifying for the current observable.

Files patched:
- `CLAUDE.md` — new "Core Rule: No Hardcoded Defaults"
- `skills/amber-workflow.md` — rewrote §Force fields as 3-tier protocol;
  removed "skill default" from simulation protocol table sources
- `skills/amber-protein-prep.md` — tleap example uses `<PROTEIN_FF>` /
  `<WATER>` / `<ION>` placeholders; added ion-water leaprc mismatch warning

## Re-running this study with dynamic FF selection

A re-run with ff19SB + OPC (or ff15ipq + SPC/Eb) is expected to produce a Tm
much closer to the experimental 315 K. The qualitative result (sharp two-state
folding, ΔH magnitude) should be preserved. Estimated cost: same as this run
(~5 hr wall time on 16 GPUs), but requires fresh system build (~30 min) since
the prmtop from `trpcage_1ns_stress` was built with ff14SB and is not reusable.

## Files in this directory

- `PLAN.md` — approved plan (locked to ff14SB+TIP3P due to system reuse)
- `PROCESS_REPORT.md` — engineering log, all SLURM jobs, bug fixes, validation gates
- `STUDY_REPORT.md` — full scientific report with results, caveats, lit comparison
- `simulations/` — pre-equil and REMD production inputs/outputs
- `analysis/` — per-temperature cpptraj outputs + thermodynamic plots
- `logs/` — SLURM stdout/stderr per job

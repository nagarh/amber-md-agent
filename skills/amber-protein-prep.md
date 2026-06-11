# Skill: amber-protein-prep

Full protein system preparation pipeline. Covers preflight → cleaning → capping → tLEaP → validation.
For ligand parametrization → load `skills/amber-ligand.md`.
For nucleic acids → load `skills/amber-nucleic_acid.md`.
For metals → load `skills/amber-metal_complex.md`.
For membranes → load `skills/amber-membrane.md`.

## Execution Model — Parallel Phases

**Always batch independent tool calls in a single message.** Each phase lists parallel (fire together) vs sequential (wait for prior results). Cuts tool call count ~60%, total prep time ~3×.

---

## PHASE 1 — Fetch + Inspect [PARALLEL]

Fire both in ONE message:
```
mcp__amber__fetch_pdb(pdb_id="<ID>", output_dir="studies/<study>/raw_pdbs")
mcp__amber__inspect_pdb(pdb_file="studies/<study>/raw_pdbs/<ID>.pdb")
```

From inspect_pdb results, record ALL of:
- Chains present
- SSBOND records → ALL disulfide pairs (both residue numbers from each record)
- `missing_residues` (REMARK 465) → lists ALL missing residues (terminal AND mid-chain); does NOT classify them
- `coordinate_gaps` → backbone distance > 2.0 Å between consecutive ATOM records = true mid-chain break (guardrail vs the ideal peptide C–N bond length ~1.33 Å, Engh & Huber 1991 stereochemistry; > 2.0 Å cannot be a bonded backbone link)
- **Classification rule (MANDATORY):** REMARK 465 entries are **terminal** if they fall outside the min/max ATOM residue range for that chain; **mid-chain** only if `coordinate_gaps` is non-empty OR the entry falls between the ATOM range min and max. Verify with: `grep "^ATOM" system.pdb | awk '{print $5, $6}' | sort -k1,1 -k2,2n | awk '!seen[$1]++{first[$1]=$2} {last[$1]=$2} END{for(c in first) print c, first[c], last[c]}'`
- **Use `coordinate_gaps` (not REMARK 465) as the primary signal for loop_model** — empty `coordinate_gaps` = no mid-chain breaks regardless of what REMARK 465 says
- HETATM → metals to keep / waters and buffer ions to remove
- Resolution, has_hydrogens, model count (NMR?)
- First residue number per chain (capping needed if ≠ 1)

**Decision point (before Phase 2):**
- Which chains to use
- Which HETATM to keep (metals) / remove (waters, buffer ions)
- Which missing residues need loop_model vs discard+cap
- H-stripping needed? (has_hydrogens=True OR resolution < 1.2 Å — sub-Ångström resolution at which crystallographic H atoms become routinely resolvable, IUCr definition of atomic/sub-Å resolution; such structures often carry refined H that must be stripped and rebuilt by tLEaP/reduce)

---

## PHASE 2 — Clean + Strip [PARALLEL]

Create subdirs first (clean_pdb fails if output dir missing):
```bash
mkdir -p studies/<study>/system studies/<study>/logs studies/<study>/raw_pdbs
```

Fire in ONE message:
```
mcp__amber__clean_pdb(pdb_file="raw.pdb", output_file="system/clean.pdb")
```

After clean_pdb returns:
```bash
# Strip CONECT (always):
grep -v "^CONECT" system/clean.pdb > system/clean_nocon.pdb

# Strip remaining HETATM (pdb4amber --dry only removes waters, not metal ions like NA/MG/ZN):
# Protein-only: strip all HETATM
grep -v "^HETATM" system/clean_nocon.pdb > system/clean_nohet.pdb
# Protein+ligand: extract ligand FIRST (→ amber-ligand.md), THEN strip HETATM from protein file

# Check H count:
grep "^ATOM" system/clean_nohet.pdb | awk '$3 ~ /^[0-9]*H/' | wc -l
```

If H count > 0, strip H:
```bash
awk '!/^ATOM/ || $3 !~ /^[0-9]*H/' system/clean_nohet.pdb > system/clean_noH.pdb
```

---

## PHASE 3 — CYX Rename + Modified Residues

From SSBOND records (Phase 1), rename ALL disulfide CYS → CYX in PDB:
- Extract BOTH partners from every SSBOND line
- Use Python: `line[:17] + "CYX" + line[20:]` for matching residues
- Strip all CONECT lines first, then add CONECT records for each CYX SS pair
- NEVER use explicit `bond mol.X.SG mol.Y.SG` tLEaP commands — fail with leaprc.gaff2

Handle modified residues (convert HETATM → ATOM):

| Modified | → Standard | Action |
|----------|-----------|--------|
| SEP | SER | rename, drop phosphate O/P atoms |
| TPO | THR | rename, drop phosphate O/P atoms |
| MSE | MET | rename, rename SE→SD |
| CSO | CYS | rename, drop OD (sulfinyl O) |

---

## PHASE 4 — Loop Model + Cap [PARALLELIZE per independent chain]

**Mid-chain gaps** (REMARK 465, backbone distance > 2.0 Å):
```
mcp__amber__loop_model(pdb=..., missing="A:86-91", uniprot="<ID>", out=..., auto_low_confidence="accept")
```
- AlphaFold cached after first download — instant on reruns
- Geometric gap extension active: if gap_dist > n_residues × 3.8 Å, loop_model auto-extends range to include stub residues (3.8 Å = canonical CA–CA virtual bond / Cα–Cα spacing of consecutive residues in a trans-peptide chain; standard coarse-grained backbone geometry, e.g. Levitt 1976 / PULCHRA)
- Independent chains → fire loop_model calls in ONE message

**After each loop_model call — read meta.json and log to PLAN.md:**
```
<out>.meta.json  →  contains: source, plddt_mean, plddt_min, residues_grafted
```
Write to PLAN.md §Loop modeling:
```
| Range | Source | pLDDT mean | pLDDT min | Low-conf accepted? |
|-------|--------|-----------|-----------|-------------------|
| A:290-301 | AlphaFold | 62.3 | 48.1 | yes |
```
Low pLDDT (< 70) loops → note in PLAN.md to apply position restraints during minimization/equilibration, and exclude from RMSD reference selection in analysis. (pLDDT < 70 = AlphaFold low-confidence band, per Jumper et al. 2021 / AlphaFold DB confidence bands: 90+ very high, 70–90 confident, 50–70 low, < 50 very low.)

**Terminal missing / truncated** (first residue ≠ 1):
```
mcp__amber__cap_protein(input_pdb=..., output_pdb=...)
```
After cap_protein: verify TER records preserved — re-add if missing (cap_protein may strip TER).

**Orphan stub atoms** (residue exists but has only N — no CA/C): remove before tLEaP or it creates split-residue errors.

---

## PHASE 5 — Propka3 [SINGLE CALL — cached]

```
mcp__amber__run_propka3(pdb_path="system/protein_cyx.pdb", pH=<chosen_pH>)
```

**Choose pH per study via the tier protocol — never hardcode.** The pH governs propka3 protonation assignment and is a tunable scientific parameter. Justify it for the specific target:
- **Tier 1 — Lit precedent:** the pH used in MD/experimental studies of *this* protein in *its* actual physiological compartment (from Step 2b/2c pubmed search).
- **Tier 2 — Amber manual** (`rag_query`) if Tier 1 empty.
- **Tier 3 — Training knowledge** with explicit `Tier 3` note. The table below lists candidate starting values by cellular location, NOT defaults — select and justify per target.

Log the chosen pH + its source in PLAN.md.

| Location | Candidate pH |
|----------|----|
| Extracellular / blood / secreted | 7.4 |
| Cytoplasm / nucleus | 7.0–7.2 |
| Endosome | 5.5–6.5 |
| Lysosome | 4.5–5.0 |
| Mitochondrial matrix | 7.8 |

propka3 is **cached** (same PDB + same pH → instant reuse, no rerun).

**Metal-coordinating HIS override** (after propka3) — 2.5 Å is the upper bound for a direct His-N→metal coordination bond (typical Zn/Mg–N(His) coordination distances ~2.0–2.3 Å; Harding 2006 metal–ligand distance survey, Acta Cryst. D62:678):
- ND1→metal < 2.5 Å → HIE (override propka regardless)
- NE2→metal < 2.5 Å → HID (override propka regardless)

---

## PHASE 6 — Apply Protonation [SEQUENTIAL]

```
mcp__amber__apply_protonation_overrides(
  pdb_in="system/protein_cyx.pdb",
  pdb_out="system/protein_protonated.pdb",
  overrides=[...]
)
```

After:
- Verify TER count = number of chains (re-add if stripped)
- Verify H count = 0 (strip if any remain)
- Log all non-default protonation in PLAN.md §Protonation states

---

## PHASE 7 — Net Charge Check + Write tLEaP [SEQUENTIAL]

### Phase 7a — Net charge check (SLURM, CPU, 5 min)

**MANDATORY before writing the full tLEaP.** Determines which counter-ion to use for neutralization.
Per Amber24 §13.6.5 p.249: when `numIon = 0`, tLEaP auto-neutralizes — but `ion2 must not be specified` and `ion1 must be opposite in charge to unit`. Never add both `Na+ 0` and `Cl- 0`.

Write a charge-check tLEaP script with the SAME preamble as the full script (same sources, same loads, same combine) but NO solvatebox — just `charge <unit>` then `quit`:

```
mcp__amber__write_tleap(output_path="system/charge_check.in", commands="""
<same source/loadamberprep/loadMol2/loadPdb/combine as full tLEaP>
charge complex
quit
""")
```

Submit via SLURM (never on login node — tLEaP needs Amber module):
```
mcp__amber__write_slurm(
  output_path="system/run_charge_check.sh",
  commands="cd /abs/path/system && tleap -f charge_check.in > charge_check.log 2>&1",
  job_name="charge_check_<study>", gpus=0, walltime="00:05:00"
)
submit_slurm(...)
wait_for_slurm_job(...)
```

Parse result — use `mcp__amber__read_file_head` or `Read` tool on `system/charge_check.log`, grep for:
```
Total unperturbed charge:   -7.00000
```
Agent reads the value directly. Round to nearest integer → pick ion:
- net charge < 0 → `Na+`
- net charge > 0 → `Cl-`
- net charge = 0 → skip addIons

No code execution. Agent parses inline from log text.

### Phase 7b — Write full tLEaP [SEQUENTIAL]

Use `ion` from Phase 7a:

```
mcp__amber__write_tleap(output_path="system/tleap.in", commands=<commands>)
```

**Protein-only template:**
```
source leaprc.protein.{protein_ff}
source leaprc.water.{water_model}
mol = loadPdb system/protein_protonated.pdb
addIons mol {ion} 0
solvatebox mol {WATER_BOX} {padding}
saveAmberParm mol system/system.prmtop system/system.inpcrd
quit
```

Fill from PLAN.md §Force fields (tier protocol, never hardcode):
- `{protein_ff}` → e.g. `ff14SB`, `ff19SB` (from PLAN §Force fields)
- `{water_model}` → e.g. `tip3p`, `opc`, `tip4pew` (matched to protein FF)
- `{WATER_BOX}` → e.g. `TIP3PBOX`, `OPCBOX`, `TIP4PEWBOX` (must match water model)
- `{padding}` → Å from PLAN §Box
- `{ion}` → `Na+` or `Cl-` from Phase 7a charge check

**Order: addIons BEFORE solvatebox** — Amber24 §13.6.5 p.249: ions placed on Coulombic grid around unsolvated solute. Then solvatebox wraps water around protein+ions. Reverse order (solvate then addIons) causes addIons to delete water molecules displaced by ions.

Where `{ion}` = `Na+` (net charge < 0) or `Cl-` (net charge > 0). If net charge = 0, skip addIons entirely.

`numIon = 0` means **target net charge = 0** (neutralize) — tLEaP adds however many ions needed to reach charge 0. It is NOT a count of 0 ions. (Amber24 §13.6.5 p.249)

**addIons correct unit names:**
- Na+, Cl-, K+ (sign notation correct)
- MG (not Mg2+), ZN (not Zn2+), CA (not Ca2+), MN (not Mn2+)

**Disulfides:** CONECT records in protein PDB — never `bond mol.X.SG mol.Y.SG`.

**Mixed systems** (protein + nucleic acid / membrane / carbohydrate): load respective skills for correct leaprc source order and FF choices.

Always use absolute paths in tLEaP scripts.

---

## PHASE 8 — Submit + Wait [USE wait_for_slurm_job]

```
mcp__amber__write_slurm(
  output_path="system/run_tleap.sh",
  commands="cd /abs/path/system && tleap -f tleap.in > tleap.log 2>&1",
  job_name="tleap_<study>", gpus=0, walltime="00:30:00"
)
mcp__amber__submit_slurm(script_path="system/run_tleap.sh")
mcp__amber__wait_for_slurm_job(job_id="<ID>", poll_interval=5, timeout=1800)
```

**Use wait_for_slurm_job — NOT check_slurm_job loop.** 5s polling, no LLM round-trips.

---

## PHASE 9 — Validate [PARALLEL]

Fire both in ONE message:
```
mcp__amber__validate_tleap(log_file="system/tleap.log")
mcp__amber__list_files(directory="system", pattern="system.*")
```

**validate_tleap FAIL:** always check `Errors = 0` in tleap.log directly — tool false-FAILs on protein long-bond warnings (grafted loops, benign).

**Pass criteria:** system.prmtop AND system.inpcrd both exist and > 0 bytes.

---

## IDP / intrinsically-disordered systems

Reproducing IDP properties (radius of gyration, end-to-end distance, secondary-structure populations) is an **enhanced-sampling + force-field** problem, not a single-trajectory structural one:
- Rg and ensemble averages need a **converged conformational ensemble** (µs explicit MD or T-REMD / REST2), NOT a short MD.
- Standard **ff19SB + TIP3P over-compacts IDPs** — use an IDP-optimized combination (TIP4P-D water, or a99SB-disp / ff19SB+OPC with caution), justified per study via the tier protocol.

Flag any IDP / disordered system as requiring this protocol **before** attempting an Rg / ensemble reproduction.

---

## Known Bugs Checklist

| Bug | Fix |
|-----|-----|
| CYS→CYX: bond commands alone insufficient | Rename in PDB before tLEaP |
| CONECT + explicit bond = duplicate FATAL | CONECT-only — never combine |
| bond commands fail with leaprc.gaff2 | CONECT-only for all disulfide systems |
| cap_protein strips TER records | Re-add TER after cap_protein |
| apply_protonation_overrides strips TER | Re-add TER after apply_protonation_overrides |
| clean_pdb H-stripping unreliable | Always manually check + strip H after clean |
| NMR MODEL record has trailing spaces | Use `awk '/^MODEL[[:space:]]+1[[:space:]]*$/'` not grep |
| SSBOND extraction: only one partner | Extract BOTH residue numbers from each SSBOND line |
| CONECT serials stale after cap renumbering | Rebuild CONECT from actual SG atom serial numbers |
| Orphan stub atoms (N-only residue) | Remove before tLEaP — causes split-residue FATAL |
| pdb4amber --no-renum not in Amber 24 | Remove from any script |
| addIons: wrong metal names | MG/ZN/CA/MN not Mg2+/Zn2+/Ca2+/Mn2+ |
| validate_tleap false-FAIL on long bonds | Check Errors=0 in tleap.log directly |
| ZN-coord HIS wrong tautomer | ND1→ZN=HIE; NE2→ZN=HID — override propka |
| HETATM metals survive pdb4amber --dry (NA/MG/ZN etc.) | MDAnalysis reads them as resid=1 with no CA → cap_protein crash; strip all HETATM after clean (Phase 2) |
| addIonsRand before solvatebox | FATAL "No solvent present" — addIonsRand needs water first. Use addIons (Coulombic, pre-solvation) OR addIonsRand after solvatebox |
| HETATM records after END in PDB | tLEaP stops at first END → metals/ligands silently dropped. ALWAYS grep -v "^END" from protein PDB before appending HETATM; add single END at bottom |
| Wrong ion sign for neutralization | Check `charge mol` output BEFORE addIons. Positive charge → need Cl-. Negative charge → need Na+/K+. Using wrong sign → tLEaP warns and skips neutralization silently |
| Mg2+ at RNA coordination distance | tLEaP tries to make covalent bonds O-Mg2+ → "Could not find bond parameter". Strip Mg2+ from PDB before loadPdb; add as free counterions via addIons after solvation |


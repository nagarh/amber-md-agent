# Skill: amber-nucleic_acid

Simulation of DNA and RNA systems in Amber 24.

---

## CRITICAL: RNA Timescale Warning

**RNA hairpin MD at ns timescales will show structural drift regardless of force field.**

Evidence from multiple RNA MD studies:
- OL3+LJbb+OPC, 5ns: RMSD 5.18 Å (1K2G 22-mer)
- OL3+TIP3P, 5ns: RMSD 6.89 Å (1K2G 22-mer) — LJbb helps but both drift
- OL3+LJbb+OPC, 25ns: RMSD 13.47 Å — complete unfolding
- OL3+LJbb+OPC, 10ns: RMSD 12.40 Å (1RFR 30-mer longer stem) — worse, not better

**What this means:**
- Sim length/timescale and the µs/enhanced-sampling vs 5–50 ns regime must be justified per study; the ranges shown are illustrative of the regime, not defaults — record the chosen length in PLAN.md via the 4-tier protocol.
- RNA stability assessment: need µs simulations or enhanced sampling (REST2, metadynamics)
- RNA structural analysis (local dynamics, helical params, torsions): 5-50 ns fine
- Short hairpins (≤8 bp) prone to fraying; stem fraying (not tetraloop) is main failure mode (heuristic guardrail, from the RNA MD evidence above)
- OL3+LJbb+OPC better than OL3+TIP3P but still insufficient for long-timescale stability

> **OL3 RNA-tertiary reliability is motif-dependent.** Rigid tertiary cores reproduce well over short MD (tRNA L-shape, GNRA tetraloops, G-quadruplex, duplexes). **Flexible pseudoknot loop-helix base-triples drift** to the tolerance edge on the same timescale. Two practices: (a) for an NMR-determined flexible RNA, grade RMSD against the **NMR ensemble spread (typically 3–5 Å)**, not a single deposited model; (b) treat pseudoknots / base-triples as an OL3 stress point — use longer sampling / ensemble comparison, and report stems vs loops separately.

---

## CRITICAL: How to Build RNA/DNA Systems

**NEVER use tLEaP `sequence` command for structural studies.** Builds a linear extended chain — not a folded hairpin/duplex. Biases ALL observables.

**Always use `loadPdb` with experimental structure:**
```
mol = loadPdb structure.pdb
```
**Exception:** `sequence` acceptable for short duplexes equilibrating to B-form (e.g., 12bp DNA where B-form is the obvious minimum). For RNA hairpins/tetraloops: always use NMR/crystal PDB.

Known issue: RNA UUCG built from sequence → linear chain → measured "RMSD" was folding dynamics, not stability.

---

## System Type Identification

Nucleic acid if:
- `inspect_pdb()` returns `nucleic_acids = True`
- PDB contains: `DA, DT, DG, DC` (DNA) or `A, U, G, C, RA, RU, RG, RC` (RNA)
- User mentions "DNA", "RNA", "duplex", "oligonucleotide", "aptamer", "G-quadruplex"

---

## Force Field

For leaprc details and Table 3.1/3.2 → `rag_query("DNA OL21 RNA OL3 LJbb leaprc recommended Table 3.1 3.2")`.

Every FF, water model, ion model, and salt concentration must be justified PER STUDY via the 4-tier protocol (Tier-1 lit → Tier-2 Amber 24 manual via `rag_query` → Tier-3 training → always manual validation) and recorded in PLAN.md — none of the values below is a default.

**DNA FF candidates:** `source leaprc.DNA.OL21` (OL21) vs `source leaprc.DNA.bsc1`. Tier-1 evidence: OL21 supersedes bsc1 (Zgarbová et al. JCTC 2021); bsc1 (Ivani et al. 2016).
**RNA FF candidates:** `source leaprc.RNA.OL3` (OL3) vs `source leaprc.RNA.LJbb` (LJbb with OPC, reported better NMR populations; Bergonzo & Cheatham 2015 = Tier-1 evidence).
**Water candidate:** `source leaprc.water.opc` (OPC). Tier-1/2 candidate for NA; justify per study.
**Ion model candidate:** K+/Cl- (loaded with leaprc.water.opc); Joung-Cheatham parameters (JPCB 2008) are a Tier-1 candidate — confirm per study. Neutralize syntax example: `addIons mol K+ 0`.
**Salt:** 150 mM is a Tier-1/2 candidate; justify per study. Illustrative only: `addIons mol K+ 20 Cl- 20` adds 20/20 ions — but this COUNT is box-size dependent. Recompute the ion count per study from box volume (or SLTCAP) for the target concentration; do not copy 20/20.

---

## System Preparation

- `pdb4amber -i raw.pdb -o clean.pdb --no-conect` first
- Use `OPCBOX` (must match water model)
- DNA duplex is non-globular → `iso` flag for isotropic padding
- Terminal residues auto-renamed (DA→DA5/DA3 etc.) by tLEaP
- Check `charge mol` = 0 after addIons

For tLEaP template → `rag_query("tLEaP solvateBox addIons saveAmberParm DNA RNA")`.

---

## Simulation

Use the min→heat→NPT→prod sequence from `amber-workflow.md`. No NA-specific mdin tuning required. The nonbonded cutoff (8–10 Å; e.g. `cut=9.0`) must be confirmed/justified per study — see `amber-workflow.md`. `dt=0.002` paired with SHAKE on H is a physics-coupled pairing (keep them together).

For RNA stability assessment: consider REST2 (`amber-rest2.md`) or GaMD (`amber-gamd.md`) for µs-equivalent sampling.

---

## Analysis Observables

**Helical parameters (cpptraj nastruct):**
```
nastruct DNA_struct noheader naout helical
```
Writes: `BP.helical` (base pair params), `BPstep.helical` (rise/twist/shift/slide), `Helix.helical` (helical params).

**Known issue:** `nastruct output file.dat` → "Not all arguments handled" FATAL. Use `naout <prefix>` NOT `output <filename>`. The prefix cannot contain dots — use `naout helical` not `naout helical.dat`.
For syntax details: `rag_query("cpptraj nastruct naout prefix output base pair parameters")`
Expected B-DNA (1BNA reference): rise 3.4±0.3 Å, twist 36±4°, minor groove ~6 Å, major groove ~11 Å.

**RMSD:** DNA RMSD > 2 Å vs crystal is normal (crystal packing) — heuristic guardrail. Helical params are the better quality metric.

---

## Prep Gotchas (stress-test findings)

**addIons correct unit names (RAG-verified, Amber manual §13.6.5):**
```
addIons mol Na+ 0       # sodium — Na+ is correct
addIons mol Cl- 0       # chloride — Cl- is correct
addIons mol K+  0       # potassium
addIons mol MG  0       # Mg2+ — must use MG not Mg2+
addIons mol MN  0       # Mn2+ — must use MN not Mn2+
addIons mol ZN  0       # Zn2+ — must use ZN not Zn2+
addIons mol CA  0       # Ca2+ — must use CA not Ca2+
```
Wrong form (tLEaP silently ignores or errors): `Mg2+`, `Mn2+`, `Zn2+`, `Ca2+`.

**5'-terminal phosphate on first RNA residue:**
If residue 1 has `P/OP1/OP2/OP3` atoms, tLEaP `G5`/`A5` template expects 5'-OH only → FATAL extra atoms.
Strip P/OP1/OP2/OP3 from first residue before loadPdb. Keep O5' — it becomes the 5'-OH that the G5/A5 template expects. (Amber 24 manual §3.3.3 p.42: use `terminal_monophosphate.lib` only if you want to KEEP the 5'-phosphate.)

**Phosphate atom naming — OL3 vs modrna08:**
- Standard residues (A/U/G/C): `OP1`/`OP2` (OL3 convention)
- modrna08 modified bases: `O1P`/`O2P`
- Applying wrong naming to a mixed residue PDB → FATAL missing atom.

**Modified RNA bases — replacement table:**
| PDB name | Action | Note |
|----------|--------|------|
| PSU, H2U | rename → U | parm10 standard U template |
| 1MA | rename → A | |
| 5MC, OMC | rename → C; use modrna08 MRC for OMC | |
| 5MU | rename → U | |
| 2MG, 7MG, OMG | rename → G; use modrna08 N2G/M7G/MRG | 7MG needs custom frcmod for CB-N*-CR-H5 torsion |
| YYG (wybutosine) | rename → G | No modrna08 equiv; 16 non-standard atoms must be stripped |

**G-quadruplex:** OPC water (`leaprc.water.opc` + `OPCBOX`) is a Tier-2 candidate validated in Manual §3 for quadruplex DNA — confirm per study and record in PLAN.md (not a directive).
**K+ channel ions in G-quadruplex:** structural — KEEP them. Do not remove as "crystallographic".

**NMR RNA:** channel ions are not deposited as HETATM — tLEaP addIons places them from grid.

## Common Errors and Fixes

| Error | Fix |
|---|---|
| `Could not find residue type DA` | Check PDB names; pdb4amber handles renaming |
| `Non-integer total charge` | `addIons mol K+ 0` before box |
| `SHAKE failure` at step 1 | Atom overlap — increase maxcyc |
| Density < 0.90 after NPT (heuristic guardrail) | Extend equil; one illustrative remediation is a tighter barostat coupling such as taup=0.5 — justify per study |
| `nastruct` no output | Ensure phosphate atoms present; check `parm` loaded |
| `does not have a type` on modified base | Wrong atom name convention; check OP1/OP2 vs O1P/O2P |
| `Extra atoms in residue SIA` | Strip C10/C11/O10 from NeuAc before tLEaP |

---

## References

- OL21: Zgarbová et al. JCTC 2021, DOI: 10.1021/acs.jctc.0c01350
- bsc1: Ivani et al. Nature Methods 2016, PMID: 26569599
- OPC+NA: Bergonzo & Cheatham, JCTC 2015, PMID: 26575892
- JC ions: JPCB 2008, PMID: 18593145

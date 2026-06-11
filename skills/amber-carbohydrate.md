# Skill: amber-carbohydrate

Simulation of carbohydrate systems (monosaccharides, oligosaccharides, glycoproteins, GAGs) in Amber 24 using GLYCAM06.

---

## Known GLYCAM06 One-Letter Sugar Codes (validated)

Pattern: `[linkage_pos][sugar_letter][A=alpha|B=beta]`

| Sugar | Letter | Example residues | Study |
|---|---|---|---|
| Glc (glucose) | G | `4GB` (4-β), `0GB` (term-β), `4GA` (4-α) |
| GlcA (glucuronic acid) | Z | `3ZB` (3-β for HA), `0ZB` (term-β) |
| GlcNAc (N-acetylglucosamine) | Y | `0YB` (term-β), `0YA` (term-α) |
| Gal (galactose) | L | `4LB`, `0LB` | (not tested) |
| Man (mannose) | M | `4MA`, `0MA` | (not tested) |

**Hyaluronate disaccharide:** `sequence { 3ZB 0YB }` (beta-1,3 GlcA-GlcNAc) ← verified ✓

---

## System Type Identification

Carbohydrate system if:
- PDB contains GLYCAM residue names (0GB, 4GA, 0MA, etc.)
- User mentions "glycan", "sugar", "carbohydrate", "saccharide", "GAG", "heparin", "hyaluronic acid", "chitosan", "cellulose", "glycoprotein"

---

## Force Field

For leaprc details → `rag_query("GLYCAM06j leaprc carbohydrate water TIP3P")`.

**GLYCAM06j** (`leaprc.GLYCAM_06j-1`) is the near-mandatory carbohydrate force field — confirm it exists in Amber 24 via `rag_query("leaprc.GLYCAM_06j-1")` (always-validation step) before committing it in PLAN.md.

Water and ion models are tunable — justify per study via the 4-tier protocol and record tier citations in PLAN.md, not as bare defaults:
- **Water model** — tip3p is a Tier-1/2 candidate (GLYCAM06 was originally parameterized/validated against TIP3P, with TIP5P also examined in the original work); justify the choice (tip3p vs OPC vs TIP4P-Ew) per study. If a protein FF is co-loaded, match water to its parameterization (e.g. ff19SB pairs with OPC).
- **Ion model/type** — Na+/Cl- are Tier-1/2 candidates (loaded with `leaprc.water.<model>`); justify the ion *parameter set* (e.g. Joung–Cheatham monovalent vs 12-6-4 polarizable for divalents) AND whether physiological salt (beyond bare neutralization) is needed per study.

```
source leaprc.GLYCAM_06j-1     # confirm via rag_query("leaprc.GLYCAM_06j-1") — always-validation step
source leaprc.water.tip3p      # water model: justify per study (tip3p/OPC/TIP4P-Ew) — see PLAN.md tier protocol
```

**CRITICAL — 1-4 scaling:** GLYCAM_06j uses SCEE=1.0, SCNB=1.0 (no scaling of 1-4 interactions). Differs from protein FFs. Do NOT mix GLYCAM06 with protein FF without checking compatibility. (This is REQUIRED GLYCAM physics — not a tunable choice.)

> **CRITICAL — GLYCAM06 is NOT compatible with implicit GB.** Running a GLYCAM sugar with `igb>0` blows up: EGB absurd (≈ −60000 kcal/mol for one glucose), 1-4/VDW/EELEC = 0, BOND/TEMP overflow — GLYCAM atom types lack proper GB radii. **Always use explicit solvent (TIP3P).** For tiny single-sugar systems use NVT throughout + `-AllowSmallBox` (avoids the GPU small-box / NPT-reorg crash); NVT (no volume change) sidesteps the box-reorg failure entirely.
>
> **Ring-pucker analysis:** `cpptraj pucker … cremer amplitude` is ambiguous for 6-rings — col2 is the phase φ (scatters ±180° at the ⁴C₁ pole where φ is undefined), col3 "[Amp]" is NOT Q in Å. Also `strip` keeps **topology order** (0GB ring = C1,O5,C5,C4,C3,C2), not ring connectivity. **Compute Cremer–Pople Q,θ directly from coordinates with atoms in true ring order O5→C1→C2→C3→C4→C5.** Validated: β-D-Glcp ⁴C₁ → Q≈0.55 Å, θ≈15° (matches experimental ~0.55–0.59 Å).

Ions: Na+/Cl- are Tier-1/2 candidates (loaded with `leaprc.water.<model>`); justify the ion parameter set and any physiological salt per study — see PLAN.md tier protocol.

---

## System Building

### Option A: Build from sequence (simple oligosaccharides)

Cellobiose (β-1,4 glucose dimer):
```
source leaprc.GLYCAM_06j-1
source leaprc.water.tip3p      # water model: justify per study — see PLAN.md tier protocol
carb = sequence { 4GB 0GB }
solvateBox carb TIP3PBOX 10.0  # box solvent must match chosen water; padding 10.0 Å: justify per study — see PLAN.md tier protocol
saveAmberParm carb system.prmtop system.rst7
quit
```

### Option B: Load from PDB (glycoproteins, complex glycans)

**CRIT-08 — Source order: GLYCAM FIRST, then protein FF (Amber manual §13.7.3) — this ordering is REQUIRED, do NOT reorder:**
```
source leaprc.GLYCAM_06j-1     ← MUST be first (REQUIRED ordering — CRIT-08)
source leaprc.protein.ff14SB   # protein FF: justify per study (ff14SB vs ff19SB; ff19SB pairs with OPC water) — see PLAN.md tier protocol
source leaprc.water.tip3p      # water model: match protein FF parameterization; justify per study — see PLAN.md tier protocol
complex = loadPdb glycan.pdb
bond complex.<glycan_res>.<C1/O4 atom> complex.<protein_res>.<OD2/ND2 atom>
# Counterion type/parameter set AND physiological salt: justify per study — see PLAN.md tier protocol.
# `addIons ... 0` ONLY neutralizes — it adds NO bulk salt. Add explicit salt where biologically relevant
# (e.g. sulfated GAGs / heparin may require divalent or specific counterions, not just Na+).
addIons complex Na+ 0          # counterion type: justify per study (e.g. Joung–Cheatham vs 12-6-4) — see PLAN.md
addIons complex Cl- 0          # counterion type: justify per study — see PLAN.md
solvateBox complex TIP3PBOX 10.0  # box solvent must match chosen water; padding 10.0 Å: justify per study — see PLAN.md
saveAmberParm complex system.prmtop system.rst7
quit
```

PDB must use GLYCAM 3-letter codes with TER cards between residues.

**CRIT-08 — tLEaP residue index offset:** GLYCAM_06j-1.prep pre-loads ~656 template units. The molecule loaded via `loadPdb` starts at internal tLEaP index 657+. Bond commands using PDB sequential position fail — compute offset from first ATOM line index in tleap.log after loadPdb.

**CRIT-09 — NAG/GlcNAc atom name mismatch (PDB vs GLYCAM template):**
| PDB atom name | GLYCAM template name | Residue |
|---------------|---------------------|---------|
| C7 (carbonyl C) | C2N | NAG/GlcNAc |
| O7 (carbonyl O) | O2N | NAG/GlcNAc |
| C8 (methyl C) | CME | NAG/GlcNAc |

Rename in glycan PDB before tLEaP: `C7→C2N, O7→O2N, C8→CME` for all NAG/GlcNAc residues. Affects 4YB, 0YB, UYB GLYCAM residues.

**SIA/NeuAc (sialic acid) extra atoms:** Some depositors include C10/C11/O10 for aldehyde-form carboxylate. Strip these before tLEaP — GLYCAM 0SA template has no C10/C11/O10.

**Extended GLYCAM sugar code table (stress-test validated):**
| PDB name | GLYCAM code | Substitution position | Description |
|----------|-------------|----------------------|-------------|
| NAG (core, O4+O6 occupied) | UYB | 4,6-di-substituted | β-GlcNAc branching point |
| NAG (O4 occupied) | 4YB | 4-linked | β-GlcNAc internal |
| NAG (terminal) | 0YB | terminal | β-GlcNAc |
| BMA (O3+O6 occupied) | VMB | 3,6-branched | β-D-Man branching |
| MAN (O2 occupied) | 2MA | 2-linked | α-D-Man |
| GAL (O6 occupied) | 6LB | 6-linked | β-D-Gal |
| GAL (terminal) | 0LB | terminal | β-D-Gal |
| SIA (NeuAc, terminal) | 0SA | terminal | α-NeuAc |
| FUC (terminal) | 0fA | terminal | α-L-Fuc (lowercase f = L-sugar) |

### Option C: cpptraj prepareforleap (PDB preprocessing)

```bash
cpptraj << 'EOF'
parm raw_glycan.pdb
trajin raw_glycan.pdb
prepareforleap out glycan_ready.mol2 name GLYC
run
EOF
```

---

## Simulation

Use standard min→heat→NPT→prod from `amber-workflow.md`. No carbohydrate-specific mdin tuning needed.

---

## Analysis Observables

**Glycosidic torsion angles (cpptraj):**
```
dihedral phi :1@O5 :1@C1 :2@O4 :2@C4 out phi.dat
dihedral psi :1@C1 :2@O4 :2@C4 :2@C3 out psi.dat
```

---

## Common Errors and Fixes

| Error | Fix |
|---|---|
| `Could not find GLYCAM residue` | Check 3-letter code against GLYCAM naming tables; prepareforleap first |
| `Non-integer charge` | Sulfated GAGs need Na+ to neutralize |
| Missing TER cards | Add TER after each residue when loading from file |
| `sequence` wrong connectivity | Verify residue order matches desired linkage topology |
| `does not have a type` on NAG C7/O7/C8 | Rename C7→C2N, O7→O2N, C8→CME before tLEaP (CRIT-09) |
| `Bond command: cannot find atom` | GLYCAM template offset ~656 — compute correct index from tleap.log (CRIT-08) |
| `Extra atoms in residue SIA` | Strip C10/C11/O10 from SIA HETATM before tLEaP |
| `GLYCAM_06j` 1-4 scaling conflict | Source GLYCAM before ff14SB; SCEE/SCNB=1.0 must propagate |

---

## References

- GLYCAM06: Kirschner et al. JCC 2008, DOI: 10.1002/jcc.20820
- GLYCAM06j: Woods Group, University of Georgia

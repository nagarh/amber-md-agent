# Skill: amber-metal_complex

Simulation of metal ion-containing systems in Amber 24.

**Official ZAFF tutorial:** https://ambermd.org/tutorials/advanced/tutorial20/ZAFF.php

---

## System Type Identification

Metal complex system if:
- PDB contains metal ions: ZN, MG, CA, FE, MN, CU, NI, CO, NA, K, CL (as HETATM)
- inspect_pdb() shows metals: `["ZN"]` etc.
- User mentions "metalloprotein", "zinc finger", "zinc binding", "iron-sulfur cluster", "Mg2+", "Ca2+"

---

## Decision Table

| Scenario | Method | Gaussian needed |
|----------|--------|-----------------|
| Free metal ion in water (Mg2+, Ca2+, bulk Zn2+) | 12-6-4 nonbonded (frcmod) | No |
| Zinc finger (CCCC/CCCH/CCHH/CHHH/HHHH etc.), with or without GAFF2 ligands | **ZAFF** (bonded, pre-computed) | No |
| GAFF2 ligand directly coordinates metal (ZN–N, ZN–S bond at active site) | **MCPB.py** | Yes |

---

## Model A: Nonbonded (free metal ion in water)

**When to use:** Metal ion in bulk solution only — no protein zinc finger coordination.

Available frcmods (native Amber 24, `$AMBERHOME/dat/leap/parm/`):
- TIP3P: `frcmod.ions234lm_1264_tip3p`
- OPC: `frcmod.ionslm_1264_opc`
- OPC3: `frcmod.ionslm_1264_opc3`
- SPC/E: `frcmod.ions234lm_1264_spce`
- TIP4P-Ew: `frcmod.ions234lm_1264_tip4pew`

Water model, ion 12-6-4 frcmod, and box padding below are TUNABLE — justify each per study via the 4-tier protocol (CLAUDE.md "No Hardcoded Defaults"); the literals shown are placeholders, not defaults. The 12-6-4 frcmod MUST match the chosen water model (e.g. `frcmod.ionslm_1264_opc` with `source leaprc.water.opc` + `OPCBOX`), and the `solvateBox` box keyword (`TIP3PBOX`) must match the same water model.
```
source leaprc.water.tip3p             # water model — justify per study (tier protocol); pick matching frcmod + box keyword
loadAmberParams frcmod.ions234lm_1264_tip3p   # 12-6-4 frcmod — MUST match water model above
mol = loadPdb system.pdb
addIons mol Cl- 0
solvateBox mol TIP3PBOX 10.0          # box keyword must match water model; padding (Å) tunable — justify per study
saveAmberParm mol system.prmtop system.rst7
quit
```

> **CRITICAL — 12-6-4 is a TWO-STEP setup (Amber24 manual p.57).** Loading the `..._1264_...` frcmod alone does **NOT** activate 12-6-4 — tleap writes a plain **12-6** prmtop (no C4). You MUST then run **parmed `add12_6_4`** to write the `LENNARD_JONES_CCOEF` block:
> ```
> parmed -p system.prmtop -i add1264.in   # add1264.in: "add12_6_4 :MG watermodel TIP3P" then "outparm system_1264.prmtop"
> grep -c LENNARD_JONES_CCOEF system_1264.prmtop   # MUST be 1; if 0 you are silently running 12-6
> ```
> **Verify CCOEF is present before running** — without it the ion radius is too small and hydration is wrong (missing C4 gives an over-short ion–O distance and the wrong first-shell coordination number).
>
> **`lj1264` is NOT supported on `pmemd.cuda`** (manual p.411) — run 12-6-4 on **`pmemd`/`pmemd.MPI` (CPU)** or `sander`. With CCOEF present, `lj1264` auto-activates (default 1); set `lj1264=1` in mdin to be explicit.
>
> **Counterion caveat:** for a *bare-ion hydration* study, neutralizing Cl⁻ in a small box form Mg–Cl contact ion pairs that occupy first-shell sites (water CN read 4 = 6 − 2 Cl⁻). Use a large/dilute box or a net-charged box (PME background) when the observable is pure ion–water coordination.

---

## Model B: ZAFF — Zinc AMBER Force Field (zinc fingers)

**When to use:** Any zinc finger coordination motif. Works alongside GAFF2 ligands with no conflict — no extended polfile or add12_6_4 needed.

**Reference:** Peters et al., JCTC 2010, PMID:20856692
**Tutorial:** https://ambermd.org/tutorials/advanced/tutorial20/ZAFF.php

**Files:** `ZAFF.prep` + `ZAFF.frcmod` — two files cover all 12 motifs.
Not bundled with Amber 24. Download from official tutorial:
```bash
wget "https://ambermd.org/tutorials/advanced/tutorial20/files/zaff/ZAFF.prep"
wget "https://ambermd.org/tutorials/advanced/tutorial20/files/zaff/ZAFF.frcmod"
```

---

### Step 1 — Identify Coordination Motif

From ZN coordination distances (< 2.5 Å — first-shell Zn–N/Zn–S bond-length cutoff consistent with the ZAFF parameterization, Peters et al., JCTC 2010, PMID:20856692) in raw PDB:
- CYS SG → C
- HIS NE2 → H (use HID, ND1 has H); HIS ND1 → H (use HIE, NE2 has H)
- ASP OD1/OD2 or GLU OE1/OE2 → D
- WAT O → O

Count letters → motif (e.g. 3×CYS + 1×HIS(HID) = CCCH).

---

### Step 2 — ZAFF Residue Name Mapping

Full table from official tutorial:

| Center ID | Motif | ZN residue | CYS residue | HIS (HID) residue | HIS (HIE) residue | ASP residue |
|-----------|-------|-----------|-------------|-------------------|-------------------|-------------|
| 1 | Zn-CCCC (4×CYM) | ZN1 | CY1 | — | — | — |
| 2 | Zn-CCCH (3×CYM + HIE) | ZN2 | CY2 | — | HE1 | — |
| 3 | Zn-CCCH (3×CYM + HID) | ZN3 | CY3 | HD1 | — | — |
| 4 | Zn-CCHH (2×CYM + 2×HID) | ZN4 | CY4 | HD2 | — | — |
| 5 | Zn-CHHH (1×CYM + 3×HID) | ZN5 | CY5 | HD3 | — | — |
| 6 | Zn-HHHHO (2×HID + HIE + WAT) | ZN6 | — | HD4, HD5 | HE2 | — |
| 7 | Zn-HHHHO (2×HID + HIE + WAT) | ZN7 | — | HD6, HD7 | HE3 | — |
| 8 | Zn-HHDD (2×HIE + 2×ASP) | ZN8 | — | — | HE4 | AP1 |
| 9 | Zn-HHDD (2×HID + HIE + ASP) | ZN9 | — | HD8, HD9 | HE5 | AP2 |
| 10 | Zn-HHHH (4×HID) | ZN10 | — | HDD | — | — |
| 11 | Zn-HHOO (2×HID + 2×WAT) | ZN11 | — | HDA | — | — |
| 12 | Zn-HHHO (3×HIE + 3×WAT) | ZN12 | — | — | HE6 | — |

---

### Step 3 — Rename Residues in PDB

In the protonated PDB, rename all ZN-coordinating residues to their ZAFF names:
- Coordinating CYM → CYx (e.g. CY3 for CCCH motif)
- Coordinating HID → HDx; coordinating HIE → HEx
- ZN HETATM residue name → ZNx

Python snippet (adapt chain/resnum/names per system):
```python
replacements = {
    # (chain, resnum, current_name): zaff_name
    # fill from your system's coordination analysis
}

with open("protein_protonated.pdb") as f:
    lines = f.readlines()

out = []
for line in lines:
    if line.startswith(("ATOM", "HETATM")):
        chain = line[21]
        try:
            resnum = int(line[22:26])
        except ValueError:
            out.append(line)
            continue
        resname = line[17:20].strip()
        key = (chain, resnum, resname)
        if key in replacements:
            line = line[:17] + replacements[key].ljust(3) + line[20:]
    out.append(line)

with open("protein_zaff.pdb", "w") as f:
    f.writelines(out)
```

**CRITICAL:** TER record must separate protein chain from each ZN residue — tLEaP uses TER to avoid creating unwanted bonds to adjacent residues.

Verify:
```bash
grep "^TER" protein_zaff.pdb        # TER after each chain and after protein before ZN
grep "ZN[0-9]\|CY[0-9]\|HD[0-9]\|HE[0-9]" protein_zaff.pdb | head
```

---

### Step 4 — tLEaP

ff14SB is shown because ZAFF was parameterized in the ff14SB era and is the ZAFF-compatible protein FF; do NOT copy it blindly — confirm/justify the protein FF per study via `rag_query("leaprc.protein.ff14SB")` (tier protocol). Water model, ion frcmod, and box padding are likewise TUNABLE per study — the literals below are placeholders; the water box keyword and any 12-6-4 frcmod must match the chosen water model.
```
source leaprc.protein.ff14SB         # ZAFF-compatible protein FF (ff14SB era) — confirm/justify per study, do not copy blindly
source leaprc.gaff2                   # omit if no GAFF2 ligands
source leaprc.water.tip3p            # water model — justify per study (tier protocol); box keyword below must match

loadamberprep  /abs/path/ZAFF.prep
loadamberparams /abs/path/ZAFF.frcmod

# Load GAFF2 ligands if present (no conflict with ZAFF)
LIG = loadMol2 /abs/path/ligand.mol2
loadAmberParams /abs/path/ligand.frcmod

mol = loadPdb /abs/path/protein_zaff.pdb
complex = combine {mol LIG}          # omit combine if no ligands

# Explicit ZN coordination bonds
# tLEaP numbers residues 1,2,3... sequentially — NOT PDB chain/resnum
# ALWAYS run 'desc mol' first (1-min SLURM job) to get correct numbers
desc mol
# Then add bonds using tLEaP sequential residue numbers:
bond complex.N_ZN.ZN  complex.N_SG.SG    # ZN – CYx (repeat per CYS)
bond complex.N_ZN.ZN  complex.N_NE2.NE2  # ZN – HDx/HEx (if HIS in motif)

solvatebox complex TIP3PBOX 10.0     # box keyword must match water model; padding (Å) tunable — justify per study
addIons complex Na+ 0
addIons complex Cl- 0
saveAmberParm complex system/system.prmtop system/system.inpcrd
quit
```

**No ParmEd or add12_6_4 step needed** — ZAFF bonded model enforces ZN coordination geometry through bond/angle/torsion parameters directly in the prmtop.

---

### Step 5 — Validate

```
validate_tleap(log_file="system/tleap.log")
```

Also check:
```bash
grep "FATAL\|Could not find" system/tleap.log   # no missing ZAFF residue types
grep "total atoms" system/tleap.log              # sanity-check atom count
```

---

## Model C: MCPB.py (QM-derived bonded model)

**When to use:** GAFF2 ligand directly coordinates metal (ZN–N or ZN–S < 2.5 Å — first-shell bond-length cutoff per the MCPB.py/ZAFF parameterization, Li & Merz, JCIM 2016, 56:599, PMID:26913476). Requires Gaussian 09/16 or GAMESS-US.

Check availability: `which g09` or `which g16`.

Workflow:
1. `MCPB.py -i input.in -s 1` → generates Gaussian input
2. Run Gaussian
3. `MCPB.py -i input.in -s 2` → reads QM output, generates params
4. `MCPB.py -i input.in -s 3` → builds Amber topology

Reference: Li & Merz, JCIM 2016, 56:599, PMID:26913476

---

## References

- ZAFF: Peters et al., JCTC 2010, PMID:20856692; https://ambermd.org/tutorials/advanced/tutorial20/ZAFF.php
- Zn2+ nonbonded 12-6-4: Li, Song & Merz, JPCB 2015, 119:883, PMID:25145273
- MCPB.py: Li & Merz, JCIM 2016, 56:599, PMID:26913476

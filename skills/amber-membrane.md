# Skill: amber-membrane

Lipid bilayer simulation in Amber 24 using LIPID21. Use when system contains lipid molecules or user requests membrane MD.

---

## System Type Identification

Membrane system if:
- User mentions "membrane", "bilayer", "lipid", "DPPC", "POPE", "POPC", "sphingomyelin"
- PDB contains LIPID21 residue names: PA, PC, PE, PS, OL, ST, MY, CHL, SPM, PGR, PGS
- inspect_pdb() shows ligands containing lipid residue codes

---

## Force Field Selection

**LIPID21** — Tier-1/2 candidate for lipid systems; justify per study via the 4-tier protocol and record in PLAN.md (not a default):
> ILLUSTRATIVE example values — every science parameter (FF/water/ions/cut/padding/temp0/gamma_ln/nstlim/restraint_wt/lengths/write freqs) must be re-justified per study via the 4-tier protocol & recorded in PLAN.md. Do NOT copy verbatim.
```
source leaprc.lipid21
source leaprc.water.tip3p
```
- Validated for 20 lipid types, 0.9 μs each (Dickson et al. JCTC 2022) — Tier-1 precedent supporting LIPID21
- DPPC = PA tail + PC head + PA tail
- TIP3P/LIPID21 pairing is the combination validated in Dickson et al. JCTC 2022 (NOT OPC — lipid validation used TIP3P); the water model is REQUIRED to match the FF validation, so this pairing is method-mandated, not a free default
- Ions: K+/Cl- @ 0.15 M — Tier-1/2 candidate (physiological); justify per study (system charge/ionic strength) via the 4-tier protocol and record in PLAN.md, loaded with TIP3P leaprc

For force-field/leaprc details → `rag_query("LIPID21 leaprc lipid21 force field water pairing")`.

---

## Required Packages

`packmol-memgen` — at `/opt/shared/apps/amber/24/bin/packmol-memgen`.
Must run via SLURM (requires `module load amber/24`). NOT available on login node without module load.

---

## System Building (packmol-memgen)

**RAG-query lipid type and temperature before building:**
```
rag_query("LIPID21 <lipid_name> area per lipid temperature gel-liquid transition recommended")
```

Run via SLURM. Pure bilayer (NO protein) — lipid COUNT is set by `--distxy_fix`, NOT by `--lipids`:
```bash
# Pure POPC bilayer, ~50 Å XY:
packmol-memgen --lipids POPC --preoriented \
    --salt --salt_c K+ --saltcon 0.15 \
    --dist 17.5 --dist_wat 17.5 \
    --distxy_fix 50
# Output: bilayer_only.pdb (NOT bilayer.pdb — no --pdb flag for pure bilayer)
```

**Known issue:** `--lipids POPC:36` is WRONG — the `:36` is interpreted as a second lipid type named "36", causing KeyError. To set size: use `--distxy_fix <Å>`. Number of lipids is auto-determined from area-per-lipid × XY area.

With protein embedded:
```bash
packmol-memgen --pdb protein_oriented.pdb --lipids POPC \
    --preoriented --salt --salt_c K+ --saltcon 0.15 \
    --dist 17.5 --dist_wat 17.5
# Output: bilayer.pdb (protein + bilayer)
```

Key flags:
- `--preoriented`: protein already oriented along z-axis (use `--ppm` or OPM server if not)
- `--dist 17.5`: water layer thickness each side (Å)
- `--distxy_fix N`: fix XY box to N Å (pure bilayer only)

---

## tLEaP Input

packmol-memgen pre-solvates/ions; tLEaP still needed for prmtop:
```
source leaprc.lipid21
source leaprc.water.tip3p
mol = loadPdb membrane.pdb
charge mol
saveAmberParm mol system.prmtop system.rst7
savePdb mol system.pdb
quit
```

**Known issue:** packmol-memgen output has NO CRYST1 record. tLEaP's `saveAmberParm` will create an inpcrd without box → "Box parameters not found" error → atoms outside box → simulation explosion. Always set box explicitly in tLEaP:

```
source leaprc.lipid21
source leaprc.water.tip3p
mol = loadPdb bilayer_only.pdb
# MANDATORY: set box from actual atom coordinate range (setting a box is REQUIRED; the +5 Å pad below is a tunable choice)
# The +5 Å padding is a heuristic guardrail to avoid atoms-outside-box errors; justify the exact pad per study via the 4-tier protocol and record in PLAN.md (not a default)
# Measure: awk '/^ATOM/{if($7>xmax)xmax=$7; if($8>ymax)ymax=$8; if($9>zmax)zmax=$9; if($7<xmin||NR==1)xmin=$7; if($8<ymin||NR==1)ymin=$8} END{print xmax-xmin, ymax-ymin, 2*zmax}' bilayer_only.pdb
set mol box { <measured_X+5> <measured_Y+5> <measured_Z+5> }
charge mol
saveAmberParm mol system.prmtop system.inpcrd
quit
```

After setting box, ALWAYS autoimage coordinates into box before MD:
```python
# cpptraj pre-processing:
parm system.prmtop
trajin system.inpcrd
autoimage
trajout system_centered.inpcrd restart
run
```
Use `system_centered.inpcrd` as the starting coordinates for min1.

---

## Simulation Parameters — membrane-specific flags

Method-mandated flags (`barostat=1`, `nscm=0`, `ntc/ntf=2,2`, `ntp=1`) are REQUIRED for the LIPID21 protocol and kept as-is. The tunable values (`cut`, `temp0`) are Tier-1/2 candidates — justify per study via the 4-tier protocol and record in PLAN.md.

| Flag | Value | Why |
|------|-------|-----|
| `cut` | `10.0` | Tunable: Dickson et al. JCTC 2022 used a 10 Å real-space cutoff for LIPID21 (longer than typical protein 9 Å). Tier-1 candidate — justify per study in PLAN.md (not a default) |
| `barostat` | `1` | REQUIRED. Berendsen. **NOT** `2` (MC) — deforms/collapses bilayer |
| `ntp` | `1` | REQUIRED. Isotropic. LIPID21 was validated with isotropic NPT (ntp=1) and without surface tension (Dickson et al. JCTC 2022; ntp=3 needs csurften>0, NOT used in LIPID21 validation). ntp=1↔ntb=2 ensemble pairing is mandatory |
| `nscm` | `0` | REQUIRED. Disable COM removal — avoids bilayer drift artifacts |
| `ntc, ntf` | `2, 2` | REQUIRED. SHAKE on H, dt=0.002 OK (ntc/ntf must be paired; dt coupled to SHAKE) |
| `temp0` | `325.0` for DPPC | Tunable: above the DPPC gel-liquid transition Tm ~314 K (heuristic guardrail; confirm Tm and target temp per lipid type from lit / `rag_query`). Tier-1 candidate — justify per study in PLAN.md (not a default) |

**RAG-query for system-specific equilibration protocol:**
```
rag_query("LIPID21 membrane protein equilibration protocol stages restraints")
rag_query("membrane protein embedded bilayer equilibration CHARMM-GUI Amber")
```

## Pure bilayer (no embedded protein)
> ILLUSTRATIVE example values — every science parameter (FF/water/ions/cut/padding/temp0/gamma_ln/nstlim/restraint_wt/lengths/write freqs) must be re-justified per study via the 4-tier protocol & recorded in PLAN.md. Do NOT copy verbatim.

Stage sequence (method-mandated ensemble ordering): min → NVT heat (restrained lipids + water) → NPT equil (Berendsen) → NPT prod. The restraint_wt (10.0), taup (1.0) and stage lengths are ILLUSTRATIVE tunable values — justify each per study via the 4-tier protocol (lit precedent → `rag_query` Amber 24 manual → training) and record in PLAN.md.

## Membrane protein (embedded in bilayer) — CRITICAL DIFFERENCE
Fresh packmol-memgen systems generally need a multi-stage gradually-releasing restraint scheme (a simple 3-step protocol commonly FAILS). The 6-stage scheme below is **ILLUSTRATIVE, CHARMM-GUI-Amber-derived**: every step count, restraint_wt, length, dt and taup is a tunable value to be re-justified per study via the 4-tier protocol and the `rag_query` calls above (see "RAG-query for system-specific equilibration protocol"), then recorded in PLAN.md. Do NOT copy verbatim.

> ILLUSTRATIVE example values — every science parameter (FF/water/ions/cut/padding/temp0/gamma_ln/nstlim/restraint_wt/lengths/write freqs) must be re-justified per study via the 4-tier protocol & recorded in PLAN.md. Do NOT copy verbatim.

1. **min1** (5000 steps): restrain ALL non-water heavy atoms, restraint_wt=10.0
2. **min2** (10000 steps): restrain protein backbone only, restraint_wt=5.0
3. **heat NVT** (100 ps, dt=0.001): restrain protein backbone + lipid P atoms, restraint_wt=5.0, tempi=0→T
4. **equil1 NPT** (500 ps): restrain backbone + P atoms, restraint_wt=2.0, barostat=1, taup=1.0
5. **equil2 NPT** (500 ps): restrain Cα only, restraint_wt=1.0, barostat=1
6. **equil3 NPT** (1 ns): no restraints, barostat=1, taup=1.0

(The step counts, restraint_wt ladder 10/5/2/1, lengths 100 ps/500 ps/500 ps/1 ns, dt=0.001 and taup=1.0 are ILLUSTRATIVE CHARMM-GUI-derived values — re-justify each per study via the 4-tier protocol & the `rag_query` calls above; record in PLAN.md.)

Then production. Skipping stages → E_vdw blow-up at step 0 → atom explosion.

**Why:** packmol-memgen packs lipids around the protein but leaves some close contacts (lipid tail overlaps). Staged restraint release allows the lipids to relax gradually around the protein while preventing explosion. The initial VDWAALS energy check is critical. The thresholds E_vdw > 100,000 kcal/mol and Etot > 500,000 at NSTEP=0 are heuristic guardrails for detecting close-contact explosion — if Etot > 500,000 at NSTEP=0, add more minimization before heat.

For full mdin templates → `rag_query("LIPID21 minimization heat NPT equilibration production mdin")`. Apply the flag table above on top.

---

## Validation Checks

- **After packmol-memgen:** verify bilayer visually if possible; check PDB has two leaflets.
- **After tLEaP:** `Exiting LEaP: Errors = 0` required.
- **After NPT equilibration:** `validate_step(mdout, min_density=0.85, max_density=1.05)`. The 0.85–1.05 g/cc bounds are a heuristic guardrail (expected equilibrated bilayer+water density ~0.95–1.0 g/cc); adjust the acceptance window per lipid/water system and record in PLAN.md. No `SHAKE failure` / `NaN`.

---

## Analysis Observables

**Area per lipid:** `area = box_x * box_y / (n_lipids / 2)` per frame.
Expected DPPC @ 325 K: ~63 Å² (experimental).

**NMR order parameters (Scd):** cpptraj `orderparam` for acyl chain carbons.
Expected: Scd plateau ~0.2 for DPPC @ 325 K.

---

## Common Errors and Fixes

| Error | Fix |
|---|---|
| `SHAKE failure` during equil | Restraint too weak on lipids; raise the first-stage `restraint_wt` — e.g. the ~10 kcal/mol·Å² start of the ILLUSTRATIVE ladder above — and re-justify per study |
| Bilayer deformation / collapse | Ensure `barostat=1` (Berendsen) NOT `barostat=2` (MC) |
| Very low density (<0.85) | Box too large from packmol; extend NPT equilibration |
| `Errors in leap` after packmol-memgen | Check lipid residue naming; use `leaprc.lipid21` |
| packmol-memgen not found | Module not loaded; must be in SLURM job with `module load amber/24` |
| `box dimensions changed too much` during GPU NPγT equilibration | Equilibrating an under-dense packmol-memgen bilayer triggers a GPU grid-reorg failure under compression. Run **chunked NPγT** — many short restarts, each regenerating the GPU grid. Tune the chunk length DOWN until a restart survives (longer chunks fail; tens of ps typically works). Production runs fine once equilibrated. |

---

## References

- LIPID21: Dickson CJ, Walker RC, Gould IR, "Lipid21: Complex Lipid Membrane Simulations with AMBER", J. Chem. Theory Comput. 2022, 18(3):1726-1736. DOI: 10.1021/acs.jctc.1c01217, PMID 35113553
- LIPID14 (predecessor): Skjevik et al. JPCB 2012
- Barostat warning: use barostat=1 (Berendsen) for lipids (see Amber 24 manual / LIPID21 docs)
- Amber 24 manual §3 Tables 3.9 (lipid leaprcs)

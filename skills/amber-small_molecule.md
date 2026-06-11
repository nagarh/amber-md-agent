# Skill: amber-small_molecule

Standalone small organic molecule simulation in Amber 24 using GAFF2. For solvation free energy, conformational sampling, drug-like molecules in water.

For TI/FEP alchemical free energy → see `amber-ti.md`.

> **antechamber input format: use SDF/MOL2 with bond orders, NOT bare PDB, for any molecule with double bonds / amides / aromatics.** PDB lacks bond orders → antechamber perceives them from geometry and can mis-type (NMA amide came out carbonyl C→c3, O→os, N→n7 → tleap FATAL "1-4: cannot add bond"). Generate an SDF (e.g. RDKit `Chem.MolToMolFile`) → `antechamber -fi mdl` (or `-fi mol2`). Simple molecules with no ambiguous bonds (alkanes, alcohols) parametrize fine from PDB.

---

## System Type Identification

Small molecule (standalone) if:
- Organic molecule not attached to protein or nucleic acid
- User mentions "drug-like", "ligand alone", "solvation", "GAFF2 standalone", "hydration free energy"
- Single molecule or small cluster in explicit water

---

## Force Field

Both the small-molecule force field AND the water model are tunable choices — neither is a default. Justify each per study via the 4-tier protocol (Tier-1 lit precedent → Tier-2 Amber 24 manual via `rag_query` → Tier-3 training, flagged → always manual validation) and record the result in the per-study PLAN.md FF table. The tLEaP `source` lines below and in the System Building block all derive from that single PLAN.md decision — do not re-pick them inline.

- **Small-molecule FF** — GAFF2 vs GAFF vs OpenFF. GAFF2 is a Tier-1/2 candidate for drug-like organics; justify per study, record in PLAN.md (not a default). Validate the chosen leaprc with `rag_query("gaff2 leaprc small molecule")`.
- **Water model** — TIP3P vs OPC vs SPC/E vs TIP4P-Ew. For solvation/hydration free energy the water model materially changes the answer (e.g. OPC vs TIP3P give different ΔG_hyd), so it MUST be chosen, not defaulted. Justify per study via the 4-tier protocol and record in PLAN.md.

Example `source` lines once PLAN.md has justified GAFF2 + TIP3P (tunable — swap to match the PLAN.md FF table):

```
source leaprc.gaff2         # FF per PLAN.md FF table — not a default
source leaprc.water.tip3p   # water model per PLAN.md FF table — not a default
```

---

## System Building

1. Prepare PDB with H atoms (RDKit or web tools — NOT obabel, see `amber-ligand.md`)
2. Parametrize:
```bash
antechamber -i mol.pdb -fi pdb -o mol.mol2 -fo mol2 \
    -c bcc -nc <formal_charge> -at gaff2
parmchk2 -i mol.mol2 -f mol2 -o mol.frcmod
```
3. tLEaP (TEMPLATE — the `source` lines, water box, and padding are tunable; resolve all from the per-study PLAN.md FF table, do not copy literally):
```
source leaprc.gaff2         # FF per PLAN.md FF table — not a default
source leaprc.water.tip3p   # water model per PLAN.md FF table — not a default
loadAmberParams mol.frcmod
mol = loadmol2 mol.mol2
solvateBox mol TIP3PBOX 12.0   # box solvent must match the PLAN.md water-model decision (e.g. OPCBOX if OPC chosen); 12.0 A padding is tunable — rag_query the recommended padding for this molecule size / property being measured, justify per study
saveAmberParm mol system.prmtop system.rst7
```

---

## Simulation

Use standard min→heat→NPT→prod from `amber-workflow.md`. No GAFF2-specific mdin tuning needed.

For conformational sampling of floppy ligands: consider REST2 (`amber-rest2.md`) or GaMD (`amber-gamd.md`).

---

## Analysis

- Dihedral populations: cpptraj `dihedral`
- End-to-end distance for flexible chains
- Solvation ΔG: `amber-ti.md`
- Binding ΔG: `amber-mmpbsa.md`

---

## References

- GAFF2: Wang et al. JCC 2004; Bayly et al. JPCB 1993
- BCC charges: Jakalian et al. JCC 2002
- Validation: He et al. JCTC 2025 (PMID:40068154) — GAFF2/RESP on FreeSolv

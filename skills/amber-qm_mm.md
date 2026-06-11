# Skill: amber-qm_mm

QM/MM simulations in Amber 24 using built-in sqm semiempirical engine. Use for enzyme mechanisms, proton transfer, bond breaking/forming.

---

## System Type Identification

QM/MM system if:
- User mentions "QM/MM", "quantum mechanics", "enzyme mechanism", "proton transfer", "bond breaking"
- System requires modeling electronic structure (charge transfer, reaction paths)
- Metalloenzyme with explicit quantum treatment of active site

---

## Critical: qmcharge for Enzyme Active Sites

**For aspartyl/glutamyl dyads (e.g., HIV-1 protease Asp25/Asp25'):**
- Use `qmcharge = -1` (one protonated, one deprotonated — biologically correct)
- NOT `qmcharge = -2` (both deprotonated → SCF divergence, temperature collapse)
- At rest state: one Asp is protonated (charge 0), one is deprotonated (charge -1)
- During catalysis: charge may change to -2 briefly

**For single Asp:** `qmcharge = -1` (deprotonated) or `qmcharge = 0` (protonated)

**AM1 vs PM6 (system-specific observation, not a blanket rule):** On the HIV-1 protease Asp dyad specifically, AM1 produced 0 SCF warnings vs 143 for PM6. This does NOT generalize — the QM Hamiltonian must be justified per study via the tier protocol (Tier 1 lit / Tier 2 rag_query, then validate it exists in Amber 24). Transition-metal centers, for example, typically require DFTB or PM7 rather than AM1.

---

## QM Engine Options in Amber 24

| Engine | Availability | Hamiltonians |
|---|---|---|
| sqm (Amber built-in) | ✓ Always available | AM1, PM3, RM1, MNDO, PM6, PM6-D, PM6-DH+, DFTB2/3 (**NOT PM7** — see note) |
| ORCA | External (check `which orca`) | DFT, MP2, CCSD |
| Gaussian | External (check `which g09`) | DFT, HF, MP2 |

**On this cluster (verify before use):** sqm available. Gaussian not found. Check ORCA.

> **PM7 is NOT implemented in AMBER SQM v19:** `qm_theory='PM7'` → `SANDER BOMB ... Unknown method specified for qm_theory`. Valid sqm methods on this cluster: `PM3, AM1, RM1, MNDO, PM3-PDDG, MNDO-PDDG, PM3-CARB1, AM1-D*, AM1-DH+, MNDO/D, AM1/D, PM6, PM6-D, PM6-DH+, DFTB, DFTB2, DFTB3, XTB, EXTERN`. Use **PM6** (or RM1/DFTB3) — verify the method against this list before running, do not assume PM7.
>
> **`sqm` standalone needs `-O` to overwrite an existing `-o` output file** (like other Amber tools); without it sqm silently leaves the previous output in place (stale results). Always `sqm -O -i in -o out`.
>
> sqm prints the result as `Heat of formation = <value> kcal/mol` at the optimized geometry (maxcyc>0) — directly comparable to experimental gas-phase ΔfH°. PM6 ΔHf accuracy ≈ 4.6 kcal/mol AUE; NH3 and CH4 are known PM6 outliers.

---

## mdin Parameters for QM/MM

Key additions to standard mdin `&cntrl`:
```
ifqnt=1       ! enable QM/MM
qmmask='<atom_mask>'  ! atoms in QM region
qm_theory='<HAMILTONIAN>'  ! choose per study via Tier 1 lit / Tier 2 rag_query, validate it exists in Amber 24 (AM1, PM3, PM6, PM7, DFTB, MNDO); PM6 shown elsewhere only as illustration
qmcharge=0    ! net charge on QM region
spin=1        ! multiplicity (1=singlet)
```

Full example (ILLUSTRATIVE — every tunable below must be justified per study via the tier protocol; values shown are not defaults):
```
QM/MM NVT production
 &cntrl
   imin=0, irest=1, ntx=5,
   nstlim=10000, dt=0.001,    ! nstlim per study — justify via tier protocol; shown only as illustration
   ntc=1, ntf=1,           ! NO SHAKE in QM region
   ntb=1, cut=8.0,            ! cut per study — justify via tier protocol; shown only as illustration
   ntt=3, gamma_ln=2.0, temp0=300.0,  ! gamma_ln, temp0 per study — justify via tier protocol; shown only as illustration
   ifqnt=1,
   ntpr=500, ntwx=500, ntwr=2000,  ! write freqs illustrative — set per benchmark-mode storage policy (CLAUDE.md) or analysis needs
 /
 &qmmm
   qmmask=':<residue_list>',
   qm_theory='<HAMILTONIAN>',  ! per study — Tier 1 lit / Tier 2 rag_query, validate in Amber 24; PM6 is illustration only
   qmcharge=0,
   spin=1,
   qmcut=10.0,                ! qmcut per study — justify via tier protocol; shown only as illustration
   printcharges=1,
 /
```

**CRITICAL:** `ntc=1, ntf=1` — no SHAKE in QM region (QM atoms cannot have bond constraints). For QM/MM, use dt=0.001 (1 fs not 2 fs).

---

## System Setup

QM/MM doesn't require special tLEaP beyond standard setup. The QM region is defined in mdin, not tLEaP.

Standard setup:
1. Build full system normally (e.g., protein in explicit solvent; force field justified per study via the tier protocol — see PLAN.md Force fields)
2. In mdin, specify `qmmask` for atoms to treat quantum mechanically
3. QM region size is chemistry-driven and justified per study: include the reaction center plus residues directly involved in bond making/breaking and key catalytic/coordinating groups. (As a rough orientation only, such regions often fall around 20-50 atoms, but size follows the chemistry, not a fixed number.)

---

## Capability Test (Methanol in water, PM6)

Smallest valid QM/MM test: 1 methanol molecule as QM, rest TIP3P as MM.

```
# tLEaP: build methanol + TIP3P box
source leaprc.gaff2
source leaprc.water.tip3p
loadamberparams gaff2.dat
mol = loadmol2 methanol.mol2
solvateBox mol TIP3PBOX 10.0
saveAmberParm mol system.prmtop system.rst7
```

mdin for QM/MM:
```
Methanol QM/MM PM6 test
 &cntrl
   imin=1, maxcyc=500, ncyc=250,
   ntb=1, cut=8.0,
   ifqnt=1, ntc=1, ntf=1,
 /
 &qmmm
   qmmask=':1',
   qm_theory='PM6',
   qmcharge=0, spin=1,
   qmcut=10.0,
 /
```

---

## References

- sqm manual: Amber 24 Chapter 9 (Semiempirical QM/MM)
- PM6: Stewart, J. Mol. Model. 2007
- QM/MM review: Senn & Thiel, Angew. Chem. Int. Ed. 2009

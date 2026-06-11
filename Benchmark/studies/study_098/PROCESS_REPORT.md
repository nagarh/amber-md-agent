# PROCESS_REPORT — Study 098: Ubiquitin (1UBQ) 100 ns MD

## System
- PDB 1UBQ (human ubiquitin, X-ray 1.8 Å, monomeric, 76 residues Met1–Gly76)
- ff19SB / OPC water / 0.15 M NaCl, truncated-octahedron box, 10 Å padding
- His68 → HID; net charge 0; no ligands/metals/disulfides
- 4656 waters (solvonly count), 13 Na+ / 13 Cl-
- Engine: pmemd.cuda, dt 2 fs, SHAKE, 300 K / 1 bar

## Steps
| Step | Status | Job ID | Notes |
|------|--------|--------|-------|
| fetch+inspect+preflight | PASS | - | clean monomer, no fixes needed |
| propka3 (pH 7.2) | PASS | - | His68→HID only override |
| charge check | PASS | 38756 | net charge 0.000 |
| solvate count | PASS | 38757 | 4656 waters |
| tLEaP build | PASS | 38758 | Errors=0; NATOM=19777; system.prmtop (3.6 MB) + inpcrd |
| Min1 (restrained) | PASS | 38759 | NSTEP=5000 reached |
| Min2 (free) | PASS | 38760 | NSTEP=5000 reached |
| Heat 0→300 K NVT | PASS | 38761 | NSTEP=100000; final T=297 K |
| Equil NPT (Berendsen) | PASS | 38762 | NSTEP=250000; density 1.0255 g/cc; T=299.4 K — no box-change restart needed |
| Equil2 NPT (MC barostat) | PASS | 38763 | NSTEP=250000; density 1.0268 g/cc; T=301.5 K |
| Production 100 ns | PASS | 38764 | NSTEP=50,000,000; density 1.0274 g/cc; T avg 300.04 K; 455 ns/day; prod.nc 2.37 GB / 10000 frames |
| cpptraj structural | PASS | 38799 | RMSD, RMSF, Rg, tail distances |
| cpptraj IRED S² | PASS (after 1 fix) | 38800 | 72 N-H vectors; rerun added required `modes ired.vec` arg |

## Re-runs / Auto-fixes
- **IRED first attempt (job 38799)** failed: `ired` analysis errored with "No modes data specified". RAG (Amber24 p.854–855) confirmed the `ired` command requires an explicit `modes <name>` argument linking the `diagmatrix` eigenmodes, plus `orderparamfile` for S² output. Rewrote `analysis_ired.in` with `modes ired.vec` + `orderparamfile ired_s2_order.dat` → succeeded (job 38800). Structural analysis (job 38799 first cpptraj call) was unaffected and completed.

## Decisions Source
- Force field ff19SB/OPC: Amber24 manual p.33–34 (recommended), p.54 (ubiquitin benchmark). RAG-validated leaprc names.
- His68→HID: propka3 pH 7.2 (pKa 6.0 < pH).
- S² via cpptraj IRED order 2: Amber24 manual p.854–855.
- 0.15 M NaCl: physiological/NMR-buffer ionic strength; n_ion = 0.15×4656/55.5 ≈ 13.

## Software / Reproducibility
- Amber 24 (module amber/24), pmemd.cuda GPU. cpptraj (AmberTools 24). propka3.
- Single GPU (node001). RNG ig=-1 (random seed per run).

## Performance
- Production: 455 ns/day (single GPU), 100 ns in ~4.3 h wall (15480 s blocked total incl. queue).

## Energy / Temperature / Density Averages (production, mdout AVERAGES)
- Etot = -53011 kcal/mol; EPtot = -62230 kcal/mol; TEMP = 300.04 K; Density = 1.0274 g/cc; Volume = 149891 Å³.

## Convergence Summary
- Core CA RMSD (res 1-72): mean 0.886 Å, drift (1st→2nd half) 0.057 Å → converged.
- Rg: mean 11.83 Å, drift 0.009 Å → converged globular fold.
- All-CA RMSD 1.66 Å (inflated by mobile C-terminal tail).

## File Manifest
- system/: system.prmtop, system.inpcrd, protein_protonated.pdb, system_solvated.pdb, *.pka, tleap.log
- simulations/{min1,min2,heat,equil,equil2,prod}/: *.mdin, *.mdout, *.rst7, prod/prod.nc (2.37 GB)
- analysis/: rmsd_core_CA.dat, rmsd_allCA.dat, rmsf_CA.dat, rmsf_NH.dat, rgyr.dat, tail_dist.dat, tail_to_core.dat, ired_s2_order.dat, s2_by_residue.dat, *.png plots
- logs/: SLURM .out/.err per job

## Bugs Encountered
- IRED `ired` command missing `modes` argument (fixed via RAG, see Re-runs above). Lesson: cpptraj IRED requires `modes <evec_name>` + `orderparamfile` for S².

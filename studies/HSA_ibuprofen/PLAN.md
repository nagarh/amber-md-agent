# Plan — HSA_ibuprofen
Date: 2026-05-16

## System (from preflight)
- PDB: 2BXG (Bhattacharya et al.), biological unit = monomer
- Chains kept: A only (chain B = crystallographic symmetry mate, excluded)
- Ligands: IBP A2001 (Sudlow site II, subdomain IIIA — primary ibuprofen site) + IBP A2002 (secondary site, subdomain IIA region)
- Atom count (estimated): ~65,000–75,000 (protein + 2× IBP + TIP3P box)
- Special features: 17 disulfide bonds (CYS 53–62, 75–91, 90–101, 124–169, 168–177, 200–246, 245–253, 265–279, 278–289, 316–361, 360–369, 392–438, 437–448, 461–477, 476–487, 514–559, 558–567); CYS 34 = free thiol; truncated N-term (starts SER 5) + C-term (ends SER 582) → ACE/NME capping

## Force fields
| Component | FF | Reason |
|-----------|----|--------|
| Protein | ff14SB | Standard, reproduces HSA secondary structure |
| Ligand | GAFF2/BCC | NSAID with carboxyl/isobutyl groups — GAFF2 handles these well |
| Water | TIP3P | Compatible with ff14SB; standard for protein-ligand |
| Ions | Joung-Cheatham | Matches TIP3P model |

## Protonation states (at pH 7.4 — physiological)
| Residue | State | propka3 pKa | Rationale |
|---------|-------|-------------|-----------|
| HIS 9 A | HIP | 7.83 | pKa > 7.4 → protonated at physiological pH |
| GLU 244 A | GLH | 8.53 | pKa > 7.4 → buried glutamate, protonated |
| All other HIS | HID | < 7.4 | Standard deprotonated neutral form |
| CYS 34 A | CYS | 11.06 | Free thiol (only non-disulfide CYS); standard protonated |
| CYS 53,62,75,90,91,101,124,168,169,177,200,245,246,253,265,278,279,289,316,360,361,369,392,437,438,448,461,476,477,487,514,558,559,567 | CYX | 99.99 | Disulfide-bonded; propka pKa 99.99 |

## Simulation protocol
| Step | Setting | Time / cycles | Source |
|------|---------|---------------|--------|
| Min1 | restrained backbone + sidechain, 10 kcal/mol·Å² | 5000 cyc | skill default |
| Min2 | full system | 10000 cyc | skill default |
| Heat | NVT 0→300 K, Langevin γ=2, backbone restraint 5 kcal/mol·Å² | 100 ps | skill default |
| Burst density | NPT, Berendsen barostat taup=0.5, no restraint | until 0.95–1.05 g/cc + fluct < 0.02 | skill default |
| Equil2 | NPT, Berendsen taup=2.0, backbone restraint 0.5 kcal/mol·Å² | 500 ps | skill default (medium system) |
| Production | NPT, MC barostat taup=5.0, no restraint | 100 ns | DEFAULT — literature recommendation |

### Production length rationale
Literature (PMID:41696301 2026; PMID:40750639 2025; PMID:41011122 2025) consistently uses 100 ns for HSA–drug binding studies. 50 ns is skill default but 100 ns chosen to ensure convergence of binding pose and MMPBSA averages. Marked **DEFAULT**; override to 50 ns if compute budget constrained.

### Equil2 sizing: 500 ps (medium — ~70k atoms, burst expected ≤3 iter)

## Box
- Solvent: TIP3P, padding 12 Å (standard protein-ligand)
- Ions: Joung-Cheatham, neutralize-only (HSA net charge ≈ −15 e at pH 7.4 → add Na+ to neutralize)

## Analysis targets
1. Backbone RMSD (CA atoms) — complex stability
2. Ligand RMSD (heavy atoms) for each IBP separately — pose retention
3. Per-residue RMSF — binding site flexibility
4. H-bond frequency between IBP and protein residues (> 20% occupancy reported)
5. MMPBSA per-residue decomposition (idecomp=2, igb=2) — quantify which residues drive binding
6. Contact map between IBP and protein (within 4 Å)

## Literature precedent (from Step 2b pubmed search)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable / value |
|------------------------|--------|------------|-----|------------------------|
| Dimitrova et al. 2025, PMID:41011122, DOI:10.3390/ph18091251 | HSA + profen hybrids | 100 ns | not specified | stable ligand-protein complexes at Sudlow sites I/II |
| da Silva GP et al. 2026, PMID:41696301, DOI:10.1021/acsomega.5c08989 | protein-ligand | 100 ns | GAFF2/ff14SB | MMPBSA per-residue decomposition — MET, LEU, TYR as hotspots |
| Rojas JJ et al. 2025, PMID:40750639, DOI:10.1038/s41598-025-12859-x | protein-ligand (AR) | 100 ns | standard | MM-PBSA stability + residue contacts |
| Arias et al. 2026, PMID:41759210 | HIV-1 PR + inhibitor | 1 µs | ff14SB/GAFF | MMPBSA ΔG = -16.1 vs exp -14.9 kcal/mol (good agreement) |

## Method best practices (from Step 2c — MMPBSA triggered)

Triggered by: per-residue binding analysis (MMPBSA keyword in planned analysis)

| Paper (PMID, year) | Recommendation | Amber flag | Manual page | Adopted? |
|--------------------|----------------|------------|-------------|----------|
| da Silva GP 2026, PMID:41696301 | MMPBSA per-residue decomposition, 100 ns | idecomp=2 | manual p.391 | ✓ |
| Rojas JJ 2025, PMID:40750639 | MM-PBSA 1-trajectory, last ~30 ns of production | MMPBSA.py 1-traj | manual p.894 | ✓ |
| Arias et al. 2026, PMID:41759210 | MMGBSA igb=2 gives good exp agreement | igb=2 | manual p.894 | ✓ |

### Deviations from defaults (from Step 2c findings)

| Default value | New value | Reason |
|---------------|-----------|--------|
| Production 50 ns (skill default) | 100 ns | literature consensus for HSA studies; needed for stable MMPBSA averages |
| idecomp not set | idecomp=2 | per-residue GB decomposition; manual p.391 — "pairwise" not needed for single-ligand hotspot ID |

## Walltime estimates
| System size | ns/day (estimated) | This study walltime |
|-------------|---------------------|---------------------|
| ~70k atoms | ~50–80 ns/day (single A100/V100) | min+heat: ~30 min; equil2: ~30 min; prod 100 ns: ~18–48 hr; MMPBSA: ~2 hr |

## Caveats / limitations
- 1 replicate — statistical uncertainty in MMPBSA ΔG (~2–3 kcal/mol); binding hotspots more robust than total ΔG
- GAFF2/BCC charges: semi-empirical AM1-BCC charges adequate for NSAIDs but inferior to RESP
- MMPBSA neglects conformational entropy (no normal-mode correction) — use for relative ranking of residue contributions only
- IBP A2002 site assignment (primary vs secondary) inferred from crystal position, not fluorescence competition data
- Single protonation state throughout simulation; proton tautomerism of HIS/GLU not sampled
- Crystal contacts removed (monomer only) — may affect protein surface residues near chain interfaces

## Approval: APPROVED 2026-05-16

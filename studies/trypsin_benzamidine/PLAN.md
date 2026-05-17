# Plan — trypsin_benzamidine (umbrella sampling PMF)
Date: 2026-05-16

## Scientific objective
Compute ΔG_bind of benzamidine (BEN) unbinding from bovine trypsin S1 pocket via
1D umbrella sampling along reaction coordinate r = distance(BEN_COM ↔ Asp189-Cα).
Validate against experimental Ki ≈ 18 µM → ΔG_exp ≈ −6.4 kcal/mol (Talhout & Engberts 2001;
Mares-Guia & Shaw 1965 reports 1.8×10⁻⁵ M).

## System (from preflight 3PTB.pdb)
- PDB: 3PTB, 1.7 Å resolution, bovine β-trypsin + benzamidine
- Biological unit: MONOMERIC (REMARK 350)
- Chains kept: A only (residues 16–245, chymotrypsinogen numbering, 220 AA continuous)
- Apparent "chain breaks" (34→37, 67→69, 125→127, 130→132, 204→209, 217→219) are
  chymotrypsinogen numbering gaps, NOT real breaks (CA–CA = 3.76–3.84 Å, verified).
  pdb4amber renumbers contiguously.
- Atom count est: ~32 000 (protein 3 220 + BEN 18 + ~9 600 TIP3P + ions, 18 Å pad)
- Special features:
  | Feature | Handling |
  |---------|----------|
  | 6 disulfides (22-157, 42-58, 128-232, 136-201, 168-182, 191-220) | tLEaP `bond` cmds, CYS→CYX |
  | 1 Ca²⁺ (structural) | keep, parameter from Joung-Cheatham via tLEaP `ions.lib` |
  | 62 crystal waters | DROP (fresh solvation, standard) |
  | BEN ligand 0 H | skills/amber-ligand.md Branch C (CCD SDF + MCS coord-transplant) |

## Force fields
| Component | FF | Reason |
|-----------|----|--------|
| Protein | ff14SB | gold standard globular protein |
| Ligand BEN | GAFF2 + AM1-BCC, net charge +1 (amidinium) | small drug-like, cationic at pH 7 |
| Water | TIP3P | matches GAFF2 + ff14SB defaults; published US PMFs use TIP3P |
| Ions | Joung-Cheatham (frcmod.ionsjc_tip3p) | matches TIP3P |
| Ca²⁺ | Joung-Cheatham divalent (frcmod.ions234lm_126_tip3p) | divalent metal correct LJ |

## Protonation states (pH 7.0, propka3 to confirm)
| Residue | Default | Will override if propka pKa says |
|---------|---------|----------------------------------|
| Asp189 (S1 pocket) | ASP (charged) | keep — anchors amidinium of BEN |
| His40, His57, His91 | HIE | propka may flip to HID/HIP |
| All other GLU/ASP/LYS/ARG | standard | – |
| N-term Ile16 | NH3+ (charged α-amino) | trypsin's signature internal salt-bridge to Asp194 |
| BEN | cationic amidinium (+1) | pKa ≈ 11.6, fully protonated at pH 7 |

(Auto-run `propka3 -o 7.0 protein_only.pdb` before tLEaP; PLAN edited if any non-default.)

## Box
- Solvent: TIP3PBOX, **18 Å padding** (room for ligand pull to 17 Å + 1 Å buffer to image)
- Box shape: orthorhombic, with elongation along pull axis (set tLEaP `setBox` then expand z by 6 Å)
- Ions: Joung-Cheatham, neutralize (BEN +1 → add 1 Cl⁻), then +150 mM NaCl background

## Simulation protocol
### A. Bound-state equilibration (run once)
| Step | Setting | Time / cycles | Source |
|------|---------|---------------|--------|
| Min1 | restrained heavy atoms 10 kcal/mol·Å² | 5000 cyc | skill default |
| Min2 | unrestrained | 10000 cyc | skill default |
| Heat NVT | Langevin γ=2, 0→300 K, restrained 5 kcal/mol·Å² on solute | 100 ps | skill default |
| Burst NPT | barostat=1 (Berendsen) taup=0.5, unrestrained | until ρ ∈ [0.95,1.05] g/cc, fluct<0.02 | density burst |
| Equil2 NPT | barostat=1 taup=2.0, restrained 0.5 kcal/mol·Å² on solute | 500 ps | skill default |
| Pre-pull NPT | barostat=2 (MC), unrestrained | 1 ns | settle box for pull |

### B. Steered MD pull (single trajectory, generates seed configs)
- `jar=1` in mdin
- RC: r = |COM(BEN) – CA(Asp189)| via `iat<0` group definition
- Pull range: r₀(t) from 3.0 Å (bound) → 17.0 Å (bulk), 14 Å traveled
- Velocity: 0.5 Å/ns → **28 ns sMD total**
- Force constant: rk2 = 50 kcal/mol/Å² (stiff during pull only)
- Output: `dist_vs_t` (x₀, x, F, W) + snapshots every 0.5 Å for window seeding

### C. Umbrella sampling array
- **29 windows**, centers r = 3.0, 3.5, 4.0, …, 17.0 Å
- Each window:
  - 1 ns equilibration with restraint on
  - **10 ns production sampling**
  - Restraint: `&rst iat=<grp>,<grp>, r1=0, r2=<center>, r3=<center>, r4=99, rk2=10, rk3=10` (V = 10·(r−r₀)² kcal/mol — effective force constant 20 kcal/mol/Å²)
- Total sampling: 29 × 10 = **290 ns** (+ equil 29 ns)
- Submitted as SLURM array, 29 GPUs in parallel

### D. Analysis
- Per-window dumpave files → metafile for WHAM
- WHAM via Grossfield `wham` 1D (already installed? check; fall back to Amber `ndfes --mbar`)
- Bootstrap 50 resamples for PMF uncertainty
- Standard-state correction (volume integral over bound minimum):
  ΔG_bind = −ΔG_PMF − RT ln(V_bound / V° · 4π r²_PMF·avg)
  V° = 1660 Å³ (1 M)
  Use Doudou-Reddy-Roux 2009 approach: V_bound from RMSD of BEN COM in bound basin

## Production length defaults
This study type: **binding ΔG (PMF)** → 10 ns × 29 windows is the production allocation
(vs PLAN-table "binding/MMPBSA/ΔG = 50 ns × 3 rep" which is for endpoint MMPBSA, not PMF).
PMF convergence test at 5 ns vs 10 ns will report drift; auto-extend windows still
drifting > 0.3 kcal/mol up to 20 ns.

## Literature precedent (Step 2b)
| Reference (PMID, DOI) | System | Method | Result |
|------------------------|--------|--------|--------|
| Talhout & Engberts 2001 (Eur J Biochem, PMID:11168391, 10.1046/j.1432-1327.2001.01816.x) | Trypsin + BEN | ITC | Kd = 16 µM, ΔG = −6.5 kcal/mol, 298 K |
| Mares-Guia & Shaw 1965 (J Biol Chem, doi:10.1016/S0021-9258(18)97138-7) | Trypsin + BEN | enzymatic Ki | Ki = 1.8×10⁻⁵ M (18 µM) |
| Doudou Reddy Roux 2009 (JCTC, PMID:19960123, 10.1021/ct800505a) | Trypsin + BEN PMF | US + cylindrical restraint | ΔG = −5.2 kcal/mol AMBER ff99SB |
| Buch Giorgino De Fabritiis 2011 (PNAS, PMID:21709268, 10.1073/pnas.1103547108) | Trypsin + BEN binding pathway | unbiased MD + Markov SM | Kd within 1 kcal/mol of exp |
| Lai & Brooks 2025 (JCTC, PMID:40834339, 10.1021/acs.jctc.5c00807) | Trypsin + ligands | MSλD + US | benchmarks BEN unbinding PMF |

Deviation from precedent: Doudou used cylindrical restraint to flatten the unbound region.
This plan uses 1D distance only; if PMF unbound plateau is noisy/sloped, will re-do with
flat-bottom angular restraint to improve unbound sampling (RAG-query `restraint flat bottom angle`).

## Walltime estimates
~32 000-atom system → ~200 ns/day on 1× A100 (pmemd.cuda 24).
| Step | Walltime |
|------|----------|
| min+heat+equil | ~1 h |
| pre-pull equil 1 ns | 0.5 h |
| sMD 28 ns | ~3.4 h on 1 GPU |
| US array, 29 windows × 11 ns each, parallel | ~1.5 h wallclock if 29 GPUs free, otherwise queue-limited |
| WHAM + plots | minutes (login node) |

Total GPU-hours: ~325 (5 hr equil/pull + 29 × 1.5 hr × 29 GPUs serial-equiv).
Each SLURM job ≤ 24 h walltime — no walltime risk.

## Caveats / limitations
- 1D RC distance(BEN–Asp189Cα) is **not orthogonal** to other slow motions (BEN rotational
  freedom in unbound state, water reorganization in pocket). Convergence at large r may
  be slow; mitigation = sufficient sampling per window, plus angle restraint backup plan.
- TIP3P water diffusion is fast (3.4× exp) — may artifically speed unbinding kinetics
  but PMF (thermodynamic) less affected.
- Crystal waters dropped — 3PTB has 2 ordered waters in S1 pocket near BEN amidinium.
  ff14SB+TIP3P typically reorganizes correctly in ≤500 ps; equil2 covers this.
- Asp189 protonation: assumed deprotonated at pH 7. If propka returns pKa > 6.5 in
  presence of cationic BEN, may need to re-run with ASH and report.
- Single replicate. For publication, would run 3 independent sMD seeds → 3 PMFs → SEM.

## Step gating
1. Build system + ligand prep + tLEaP (no SLURM science yet, only utilities)
2. Run equil A (SLURM, 1 GPU)
3. Run sMD B (SLURM, 1 GPU)
4. Harvest 29 starting configs at window centers (cpptraj on login pyhton)
5. Launch US array C (SLURM array, 29 jobs)
6. WHAM D (login node, Python only)
7. STUDY_REPORT.md with PMF plot, ΔG_bind comparison

## Approval: APPROVED 2026-05-16

# Plan — study_087 OmpF porin in POPE/POPG bilayer
Date: 2026-06-09

## Objective
Set up OmpF porin (PDB 2OMF) — trimeric E. coli outer membrane β-barrel — embedded in
a POPE/POPG (3:1) bilayer mimicking the E. coli outer-membrane inner leaflet. Run 50 ns
production MD. Analyze (1) pore dimensions per monomer and (2) loop L3 dynamics (the
constriction loop that folds into the barrel and sets channel selectivity/conductance).

## System (from preflight)
- PDB: 2OMF (OmpF, E. coli), X-ray 2.4 Å, UniProt P02931
- Biological unit: TRIMERIC (REMARK 350: 3 BIOMT operators; asymmetric unit has 1 chain)
- Chains kept: trimer generated from chain A via BIOMT → chains A, B, C (340 residues each)
- Detergent C8E (octyl-tetraoxyethylene, crystallization additive) and 128 waters: REMOVED
- Atom count (protein, no H): 7,881 (2,627 × 3). With H + lipids + water + ions: ~120–160k (est.)
- Special features: integral membrane β-barrel trimer; no disulfides; no chain breaks;
  no missing residues. Loop L3 (~res 102–119) is the internal constriction loop.

## Force fields

### FF table

| Component | Choice | Lit precedent (PMID) | Manual page | Reason for this study |
|-----------|--------|---------------------|-------------|------------------------|
| Protein   | ff19SB | 35294337 (Khalid review; Amber OMP MD) | Amber24 §3 p.33 | Current recommended Amber protein FF; designed to pair with OPC but compatible with LIPID21 (manual p.50 example loads ff19SB+lipid21) |
| Lipids    | LIPID21 | Dickson JCTC 2022 PMID:35113553 | Amber24 §3.5 p.49–51 | Recommended Amber lipid FF; validated for 20 lipid types incl. PE & PG head groups; POPE=PA/PE/OL, POPG=PA/PGR/OL |
| Water     | TIP3P  | 35113553 | Amber24 §3.6 p.52 | REQUIRED to match LIPID21 validation (Dickson et al. validated LIPID21 with TIP3P, not OPC); method-mandated pairing, not a free default |
| Ions      | K+/Cl- (Joung–Cheatham, TIP3P-matched) @ 0.15 M | 35113553 (physiological); 35294337 | Amber24 §3.6 / §13.6.5 | Physiological KCl; K+ matches E. coli cytoplasm/periplasm; loaded via leaprc.water.tip3p ion set |

Note on lipid choice: user specified POPE/POPG. Manual canonical bacterial example is
DOPE:DOPG 3:1 (p.231); POPE/POPG is the palmitoyl-oleoyl analogue and the standard E. coli
membrane mimic. Ratio 3:1 (PE:PG) follows the manual's bacterial-membrane recommendation
and matches E. coli phospholipid composition (~75% PE, ~20% PG). packmol-memgen builds
POPE = PA(sn-1) + PE(head) + OL(sn-2); POPG = PA(sn-1) + PGR(head) + OL(sn-2).

## Protonation states
- pH chosen: 7.0 (E. coli periplasm/cytoplasm near-neutral; standard for OmpF MD). propka3 run on trimer.pka.
- propka3 log: system/trimer.pka

| Residue | State | Rationale |
|---------|-------|-----------|
| HIS21 (A/B/C) | HID | propka pKa 5.26 ≪ pH 7.0 → neutral; δ-protonated tautomer (HID) per tool rule |
| ASP127 (A/B/C) | ASH | propka pKa 7.40 > pH 7.0 → buried, protonated (tool suggested_override, consistent across 3 symmetric chains) |
| GLU296 (A/B/C) | GLH | propka pKa 9.60 > pH 7.0 → buried, protonated (tool suggested_override, consistent across 3 symmetric chains) |

All other ASP/GLU charged (pKa < pH), all LYS/ARG charged (pKa > pH). The single HIS per
chain is the only His (HIS21). The buried ASP127/GLU296 protonation follows the propka3
tool decision rules; these are model predictions and a caveat is noted in §Caveats.

## Simulation Conditions

| Condition | Value | Reason / source |
|-----------|-------|-----------------|
| Production temperature | 310 K | E. coli physiological/growth temperature (37 °C); above POPE/POPG gel-fluid transition so bilayer is fluid (POPE Tm ~25 °C, POPG Tm ~-2 °C). Tier-1 biological context |
| Pressure | 1 atm | NPT standard for condensed-phase membrane MD (Amber24 §21.6.8 p.395) |
| pH | 7.0 | see §Protonation |
| Ionic strength | 0.15 M KCl + neutralizing counter-ions | physiological; system net charge neutralized then 0.15 M salt added by packmol-memgen |

## Simulation Protocol

Membrane-protein staged restraint-release scheme (LIPID21 / CHARMM-GUI-Amber derived;
Amber24 §3.5 p.50 barostat/cutoff guidance + amber-membrane.md). Method-mandated flags:
barostat=1 (Berendsen — MC barostat collapses bilayers, Amber24 p.50), ntp=1 (isotropic,
LIPID21 validated tensionless isotropic NPT), nscm=0 (no COM removal — avoid drift),
ntc/ntf=2,2 (SHAKE, dt=0.002), cut=10.0 (LIPID21 recommended, Amber24 p.50).

| Step | Setting | Time / cycles | Source |
|------|---------|---------------|--------|
| Min1 | restrain all non-water heavy atoms (protein+lipid) @ 10 kcal/mol·Å² | 5,000 cyc | amber-membrane.md; Amber24 §21 |
| Min2 | restrain protein backbone @ 5 kcal/mol·Å² | 10,000 cyc | amber-membrane.md |
| Heat | NVT 0→310 K, Langevin γ=1.0, restrain backbone+lipid-P @ 5, dt=0.001 | 200 ps | Amber24 §21.6.7 p.393; gradual heat for membrane |
| Equil1 | NPT barostat=1 taup=1.0, restrain backbone+P @ 2.0, dt=0.002 | 500 ps | amber-membrane.md; Amber24 §21.6.8 |
| Equil2 | NPT barostat=1 taup=1.0, restrain Cα @ 1.0 | 1 ns | amber-membrane.md; release toward unrestrained |
| Equil3 | NPT barostat=1 taup=1.0, no restraints | 2 ns | density/area equilibration before production |
| Production | NPT barostat=1 (Berendsen, lipid-safe) taup=2.0, no restraints, dt=0.002 | 50 ns | user prompt; OmpF pore/L3 dynamics sampled on 10–100 ns (35294337) |

### Production length
- 50 ns: specified by user prompt.
- Lit context: Khalid-group OMP simulations (PMID 35294337, 36322653) sample OMP/lipid
  dynamics on tens-of-ns to µs; 50 ns is adequate for pore-radius equilibration and L3
  loop fluctuation characterization but short for large conformational transitions (caveat noted).
- gamma_ln/barostat for membrane: keep Berendsen (barostat=1) throughout — MC barostat
  deforms bilayers (Amber24 p.50). dt=0.002 with SHAKE.

## Box
- Built by packmol-memgen (NOT solvateBox — membrane system, Amber24 §12.9 p.231).
- Orientation: `--ppm` (OPM/PPM3) re-orients the barrel along the membrane normal (z).
- Water layer: 17.5 Å each side (`--dist 17.5 --dist_wat 17.5`) — ample bulk water for the
  large periplasmic/extracellular loop turns; exceeds 10 Å cut + buffer (minimum image).
- Lipids: POPE:POPG 3:1 (`--lipids POPE:POPG --ratio 3:1`), XY auto-sized to trimer footprint.
- Ions: K+/Cl- 0.15 M via `--salt --salt_c K+ --saltcon 0.15`; packmol-memgen neutralizes net charge.
- Box explicitly set in tLEaP from coordinate range (packmol-memgen output lacks CRYST1) +
  autoimage before min1 (amber-membrane.md known-issue guard).

## Analysis targets (per study objective)
- **Pore dimensions:** minimum pore radius profile along the channel axis (z) per monomer
  via HOLE-style radius or cpptraj. Proxy: cross-sectional pore radius at the L3 constriction
  zone; diameter of the eyelet (Cα–Cα distances across the constriction: L3 acidic cluster
  D113/E117 to the basic ladder R42/R82/R132 on the opposite wall). Report mean ± SD.
- **Loop L3 dynamics:** L3 (res ~102–119) backbone RMSD vs crystal (after barrel alignment),
  per-residue RMSF for L3 vs the rigid β-barrel, and L3-tip displacement timeseries.
- Supporting: whole-protein backbone RMSD (barrel stability), trimer integrity (inter-chain
  contact), bilayer area-per-lipid + thickness (membrane equilibration check).

## Literature precedent (Step 2b)
| Reference (PMID, DOI) | System | Sim length | FF | Key observable |
|------------------------|--------|------------|-----|------------------------|
| Khalid et al. 2022, PMID:35294337, DOI:10.1099/mic.0.001165 | Gram-neg OM / OMP MD review | ns–µs | atomistic+CG | OMP/lipid dynamics, methods |
| Webby et al. 2022, PMID:36322653, DOI:10.1126/sciadv.adc9566 | OmpF/OmpC OM clustering | atomistic MD | — | OMP-lipid-OMP assembly |
| Benn et al. 2024, PMID:39630873, DOI:10.1073/pnas.2416426121 | E. coli OM protein lattice | MD+AFM | — | OM mechanics |
| Brandner et al. 2024, PMID:39008538, DOI:10.1021/acs.jctc.4c00374 | E. coli OM lipid models | CG | Martini | OM lipid composition |
(No exact 2OMF/POPE-POPG atomistic Amber protocol in top hits; OmpF pore/L3 is a classic
well-characterized observable — crystal L3 folds into barrel forming the ~7×11 Å eyelet.)

## Method best practices (Step 2c — Membrane triggered, keyword "membrane/bilayer/POPE/POPG")
| Paper / source (PMID) | Recommendation | Amber flag | Manual page | Adopted? |
|--------------------|----------------|------------|-------------|----------|
| Dickson 2022 PMID:35113553 | LIPID21 with Berendsen barostat, 10 Å cutoff | barostat=1, cut=10.0 | Amber24 p.50 | ✓ |
| Dickson 2022 PMID:35113553 | Isotropic NPT, tensionless (no surface tension term) | ntp=1 | Amber24 p.50, p.395 | ✓ |
| amber-membrane.md / CHARMM-GUI-Amber | Staged restraint release for packmol-memgen close contacts | ntr=1 ladder 10→5→2→1 | — | ✓ |
| Amber24 §12.9 p.231 | packmol-memgen --ppm to orient via OPM/PPM3 | (build flag) | Amber24 p.231 | ✓ |
| Amber24 §3.5 p.50 | NO MC barostat for lipids (deforms bilayer) | barostat≠2 | Amber24 p.50 | ✓ |

### Deviations from defaults
- barostat=1 (Berendsen) used for production too (not the usual MC barostat switch) — required
  for lipid stability (Amber24 p.50). | nscm=0 (membrane drift). | cut=10.0 (lipid, not 9.0).
- ntwr small enough to checkpoint before possible GPU box-change exit (amber-workflow.md).

## Walltime estimates
| System size | ns/day (pmemd.cuda) | This study walltime |
|-------------|--------|---------------------|
| ~120–160k atom membrane | ~30–60 ns/day (1 GPU) | min+heat ~1 hr; equil ~3 hr; prod 50 ns ~1–2 days |
- packmol-memgen build is SLOW (CPU, trimer footprint): allow several hours, run via SLURM.

## Caveats / limitations
- 50 ns samples pore-radius/L3 fluctuations but NOT large gating transitions (10–100+ ns / µs).
- ASP127/GLU296 protonated per propka3 prediction (buried, pKa>pH); these are empirical
  predictions — channel electrostatics could be sensitive; flagged for review.
- POPE:POPG 3:1 is a simplified E. coli OM mimic (real OM outer leaflet is LPS, not modeled
  here — LPS atomistic params not in standard LIPID21; PE/PG inner-leaflet mimic used).
- packmol-memgen close contacts require staged restraint release; GPU "box dimensions changed
  too much" may need chunked equil restarts (amber-membrane.md).

## Approval: APPROVED 2026-06-09 (benchmark autonomous run)

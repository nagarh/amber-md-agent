# Amber MM-PBSA / MM-GBSA Endpoint Free Energy

**Trigger:** Binding free energy of protein–ligand or protein–protein complex via endpoint method.

## Concept

MM-PB(GB)SA: endpoint binding ΔG from MD snapshots. Theory → `rag_query("MMPBSA.py theory single-trajectory protocol")`.

## When to use which

- **MM-GBSA**: fast (~1s/snapshot), ranks well, absolute value typically 3–5× too negative. The implicit-solvent model (`igb=2` OBC-II shown as one option; also 5, 8) is tunable — choose the GB model per study via the 4-tier protocol.
- **MM-PBSA** (internal solver): ~10–30s/snapshot, more rigorous polar term; absolute value 2–3× too negative without entropy
- **Add NMODE** (entropy): ~30–60 min/snapshot; needed for absolute affinity; usually subsampled (every 10th frame)

## Workflow

### 1. MD trajectory (prerequisite)

Standard MD on solvated complex. Trajectory length: choose per study and justify via lit precedent / Amber manual (4-tier protocol) — MMPBSA needs enough frames for SEM convergence (≥40 snapshots; see §5 guardrail). Use `ntwx=5000` (every 10 ps → 500–5000 frames over a 5–50 ns range; CLAUDE.md-sanctioned MMPBSA write frequency). Skip first ~10–20% as equilibration (heuristic guardrail).

### 2. Generate dry topologies via ante-MMPBSA.py

```bash
ante-MMPBSA.py -p complex.prmtop \
    -c complex_dry.prmtop \
    -r receptor_dry.prmtop \
    -l ligand_dry.prmtop \
    -s ':WAT,Cl-,Na+' \
    -n ':LIG' \
    --radii=mbondi2
```
`--radii` must match the chosen `igb` (igb=2 → mbondi2; igb=5/8 → mbondi3) — set per the implicit-solvent model justified for this study; mbondi2 shown only as the igb=2 case.

**Common failure: "FileExists ... not overwriting"** — rename stale files to `.stale` (cannot `rm` per project constraints).

### 3. MMPBSA input file

For input namelist syntax → `rag_query("MMPBSA.py input file gb pb namelist igb saltcon")`.

**Radii consistency**: must match `--radii` from ante-MMPBSA.py. igb=2 → mbondi2; igb=5/8 → mbondi3.

**Frame selection**: startframe=N skips first N-1 frames. interval=K thins by factor K. Aim for ≥40 snapshots (heuristic guardrail for a stable SEM; consistent with Hou et al. 2011 JCIM 51:69 benchmark sampling).

### 4. Submission

```bash
mpirun -np 8 MMPBSA.py.MPI -O \
    -i mmpbsa.in -o FINAL_RESULTS.dat -eo per_frame.csv \
    -sp complex.prmtop \
    -cp complex_dry.prmtop -rp receptor_dry.prmtop -lp ligand_dry.prmtop \
    -y prod.nc
```

SLURM: CPU-only (no `--gres=gpu`), 8 MPI ranks, ~5 min for 40 snapshots / 30k atoms. Budget 30–60 min for 50 frames + PB.

### 5. Validation

- |ΔG|/SEM > 5 → reliable; < 3 → extend frames or trajectory (heuristic guardrail)
- Per-frame plot: check for drift/jumps (loose ligand)
- Compare GB vs PB ranking
- For absolute affinity: add NMA or QH; expect TΔS ≈ +15–25 kcal/mol for small drugs (heuristic guardrail; cf. Hou et al. 2011 JCIM 51:69 entropy estimates)

## Pitfalls

1. **Antechamber duplicate aromatic bonds** — aromatic + amidine ligands: antechamber writes some bonds twice. tLEaP errors with `1-4: cannot add bond`. Fix: Python dedupe of `@<TRIPOS>BOND` by (atom_a, atom_b). See amber-ligand.md Branch C for correct pipeline.

2. **Isolated metals (Ca²⁺, Mg²⁺)** — tLEaP `savePdb` of dry prmtop fails with 1-4 bond error. Omit if not coordinating ligand.

3. **Charged ligand polar desolvation** — cation/anion penalty large, partially cancels ΔE_elec. vdW typically dominates discrimination.

4. **STP assumption** — single-trajectory assumes complex/free receptor share same ensemble. For floppy ligands or large conformational change: use 3-trajectory.

5. **Salt concentration** — set saltcon (GB) and istrng (PB) per study to match the experimental buffer (e.g. 0.15 = 150 mM), justified via the 4-tier protocol. Leaving salt at 0.0 gives no ionic screening → too-favorable ΔG for charged ligands.

## Reference benchmark

Trypsin–benzamidine 5 ns NPT, 41 snapshots, ff14SB + GAFF2 + TIP3P:
- ΔG_GB = -41.6 ± 0.6
- ΔG_PB = -24.3 ± 0.7
- Expt ≈ -6.5
- With entropy (-TΔS ≈ +18): PB → -6.3 (matches!), GB → -24 (still off)
- Matches Hou et al. 2011 JCIM 51:69 benchmark.

## References

- Hou T, Wang J, Li Y, Wang W. "Assessing the Performance of the MM/PBSA and MM/GBSA Methods. 1. The Accuracy of Binding Free Energy Calculations Based on Molecular Dynamics Simulations." *J. Chem. Inf. Model.* 2011, 51(1):69-82. PMID:21117705, DOI:10.1021/ci100275a. — snapshot-count / conformational-entropy (TΔS) / SEM-convergence guidance.

## When to extend

- SEM > 10% of |ΔG| → extend MD (heuristic guardrail; e.g. toward a 20–50 ns range, justified per study)
- Absolute affinity: `&nmode` block, subsample every 10th frame
- Decomposition: add a `&decomp` namelist (SEPARATE from `&gb`/`&pb`) with `idecomp=2`. Known issue: `idecomp` inside `&gb` → "Unknown variable" FATAL error. Correct structure:
  ```
  &gb
    igb=2, saltcon=0.15,    ! igb (2/5/8) = implicit-solvent model; saltcon = salt conc — both tunable per study via 4-tier protocol; saltcon should match experimental buffer (e.g. 0.15 = 150 mM)
  /
  &decomp
    idecomp=2,              ! decomp scheme (1/2 per-residue, 3/4 pairwise) — pick per the analysis question
    print_res="all",
    dec_verbose=3,
  /
  ```
  REQUIRED: `&decomp` must be a SEPARATE namelist from `&gb`/`&pb` (idecomp inside `&gb` → "Unknown variable" FATAL).
  Also requires `-do DECOMP_OUTPUT.dat` flag on MMPBSA.py command line. For RAG: `rag_query("MMPBSA.py decomp namelist idecomp per-residue syntax")`
- Alanine scanning: `&alanine_scanning mutant_res="A:42,A:57"`

# Skill: amber-rest2 (REST2 / T-REMD Enhanced Sampling)

Replica Exchange with Solute Tempering (REST2) and Temperature REMD for enhanced conformational sampling. Use when standard ns-MD fails to converge (e.g., RNA hairpins, peptide folding, slow protein conformational changes).

**Validated:** charge-only REST2 with 4 replicas gives 34-53% acceptance on alanine dipeptide explicit water. T-REMD on RNA with 8 replicas gave 0.4-2.3%. **REST2 wins by 15-100× for explicit solvent.**

---

## When to Use

- RNA hairpin stability (studies 007-010 established ns-MD insufficient)
- Peptide conformational sampling (IDPs, flexible loops)
- Protein-ligand binding poses
- Any system showing RMSD drift without convergence

**REST2 (charge-only) is preferred** over T-REMD for explicit solvent — scales only solute, so fewer replicas needed.

## Convergence & starting structures (MANDATORY for population/folding observables)

A population observable (fraction helix, fraction folded, basin populations) is only meaningful once the λ=1 (physical) ensemble has CONVERGED. Two requirements:

1. **Diverse / coil multi-start, NOT a single folded conformation.** Seeding all replicas from one folded structure (e.g. an α-helix or a crystal fold) leaves the physical replica carrying start-state memory for a long time — λ-ladder round-trips mix it out only slowly. Start replicas from DIVERSE conformations spanning folded→coil (e.g. extract one frame per replica from a prior run's λ-ladder, or build coil/extended starts), so the ensemble approaches equilibrium from both sides. A single helical start + short run systematically OVER-estimates the folded population.
2. **Verify the λ=1 plateau before reading the value.** Compute the observable in time-blocks: require 1st-half ≈ 2nd-half and no monotone drift (block-SEM small). A monotone decline (or rise) means NOT converged — extend, do not report. If, once converged, the value still disagrees with experiment, that residual is a force-field signal, not a sampling artifact — classify accordingly (don't keep extending).

---

## REST2 Protocol (charge-only, validated)

### Concept
Scale solute charges by √λ → effective T_eff = T₀/λ for electrostatics. LJ unchanged. Bussi 2013 / Wang 2011 simplified variant. Works because electrostatics dominate solute-solvent coupling for polar biomolecules.

### Step 1: Choose λ ladder

**RAG-query ladder design for your system first:**
```
rag_query("REST2 lambda ladder charge scaling solute tempering acceptance rate recommended")
rag_query("REST2 number of replicas system size acceptance rate convergence")
```

The table below is a **validated example for small peptides** (aladip in TIP3P). Do NOT copy for larger systems — acceptance rates depend heavily on system size and solute polarity.

| λ | T_eff (K) | √λ (charge scale) | Note |
|---|---|---|---|
| 1.00 | 300 | 1.000 | Physical replica — always include |
| 0.75 | 400 | 0.866 | |
| 0.56 | 536 | 0.748 | |
| 0.42 | 714 | 0.648 | |

Example acceptance with this ladder for aladip in TIP3P: **34% / 42% / 53%** (acceptance increases with T_eff gap).

For larger systems (proteins, RNA): RAG-query recommended λ spacing. Fewer replicas needed with charge-only REST2 than T-REMD — but still validate acceptance ≥ 20% before production (heuristic guardrail; cf. Patriksson & van der Spoel 2008 optimal-spacing analysis, see References).

4 replicas is minimal. For production on larger systems: add λ ∈ {0.88, 0.65} for 6 replicas → uniform >50% acceptance.

### Step 2: Generate scaled prmtops via parmed

```python
import parmed
import numpy as np

# --- FILL THESE FROM YOUR SYSTEM ---
# lambdas: from RAG query "REST2 lambda ladder charge scaling recommended acceptance"
# Rule of thumb: spacing such that acceptance ≥ 20%. Fewer replicas for REST2 vs T-REMD.
lambdas = <rag: list of lambda values, e.g. [1.00, 0.75, 0.56, 0.42] for small peptide>

# solute_mask: identify from parmed or inspect_pdb — the non-water, non-ion residues
# Get N_solute_residues from parmed: sum(1 for r in parm.residues if r.name not in ('WAT','Na+','Cl-'))
# Then: solute_mask = f":1-{N_solute_residues}"
solute_mask = ":1-<N_solute_residues>"  # e.g. ":1-22" for ACE-ALA-NME; compute from system
# ---

base = parmed.load_file("system.prmtop")
solute_atoms = [i for i in range(len(base.atoms)) if base.atoms[i].idx in parmed.amber.AmberMask(base, solute_mask).Selected()]
orig_charges = [base.atoms[i].charge for i in solute_atoms]

for lam in lambdas:
    parm = parmed.load_file("system.prmtop")
    sqrt_lam = np.sqrt(lam)
    for k, i in enumerate(solute_atoms):
        parm.atoms[i].charge = orig_charges[k] * sqrt_lam
    parm.save(f"system_lambda{lam:.2f}.prmtop", overwrite=True)
```

**Verify:** atom-0 charge across λ files must scale by exactly √λ.

### Step 3: mdin (shared across all replicas)

**RAG-query before writing:**
```
rag_query("REST2 H-REMD mdin nstlim numexchg recommended convergence")
```

```
REST2 H-REMD production
 &cntrl
   imin=0, irest=1, ntx=5,
   ntt=3, temp0=<rag/justify: base ladder temperature T0, typically the experimental/physiological T of the study; must equal the basis of the T_eff column (T_eff = T0/lambda)>, gamma_ln=<rag: "REST2 gamma_ln recommended NVT">,
   ntc=2, ntf=2, dt=<rag: "H-REMD timestep recommended">,
   ntb=1, cut=<rag: "REST2 NVT cutoff recommended">,
   ntpr=<benchmark-mode default 5000; per CLAUDE.md storage-conservative defaults>, ntwx=<rag: "REST2 trajectory frequency">, ntwr=<benchmark-mode default 50000; per CLAUDE.md storage-conservative defaults>, ioutfm=1,
   ig=-1,
   nstlim=<rag: "REST2 steps per exchange recommended">,
   numexchg=<rag: "REST2 numexchg total exchanges convergence">,
 /
```

**Critical:** `ntb=1` (NVT) required — H-REMD does NOT support NPT.

**Known issue:** `pmemd.cuda.MPI -ng N -groupfile groupfile` WITHOUT `-rem 3` exits code 1 silently — all output files created but 0 bytes. `-rem 3` is REQUIRED for H-REMD. Always include it.

### Step 4: groupfile (one line per replica, each with its own prmtop)

```
-O -i rest2.mdin -p system_lambda1.00.prmtop -c equil.rst7 -o rest2.0.out -r rest2.0.rst7 -x rest2.0.nc
-O -i rest2.mdin -p system_lambda0.75.prmtop -c equil.rst7 -o rest2.1.out -r rest2.1.rst7 -x rest2.1.nc
-O -i rest2.mdin -p system_lambda0.56.prmtop -c equil.rst7 -o rest2.2.out -r rest2.2.rst7 -x rest2.2.nc
-O -i rest2.mdin -p system_lambda0.42.prmtop -c equil.rst7 -o rest2.3.out -r rest2.3.rst7 -x rest2.3.nc
```

### Step 5: Launch

```bash
mpirun -np 4 pmemd.cuda.MPI -ng 4 -groupfile groupfile -rem 3 -remlog rem.log -remtype rem.type
```

`-rem 3` = Hamiltonian REMD. NOT `-rem 1` (that's T-REMD).

---

## T-REMD Setup (Temperature Replica Exchange)

**RAG-query before setting up T-REMD:**
```
rag_query("T-REMD temperature replica exchange setup ladder spacing acceptance rate")
rag_query("T-REMD genremdinputs.py temperature ladder generation")
```

Key: for explicit solvent in 100 K range need **30-40 replicas** (solvent heat capacity dominates). Spacing: ΔT ≈ 2.4 × √(T / N_atoms_solute) (Patriksson & van der Spoel 2008).

**Known issue:** T-REMD mdin MUST use `irest=0, ntx=1, tempi=T[i]` — NOT `irest=1, ntx=5`. Reading velocities from a 300K equilibration restart for higher-T replicas causes silent failure (pmemd exits code 1 after initialization, all output files 0 bytes). Each replica needs fresh Maxwell velocities drawn at its own temperature.

---

## Practical Notes for This Cluster

**CRITICAL (studies on RNA REMD):**
- pmemd.cuda.MPI REMD requires **EVEN number of replicas** (7 fails silently — empty mdout, exit 1)
- Use `mpirun` NOT `srun` — OpenMPI not built with PMI on this cluster
- `-rem 1` (T-REMD) or `-rem 3` (H-REMD) goes on **cmd line only**, NOT in groupfile

**`skinnb=2.0` is NOT a valid &cntrl key in pmemd Amber 24** — old docs are wrong (known issue).

**Working SLURM template (REST2, 4 GPU):**
```bash
#SBATCH --partition=defq --nodes=1 --ntasks=4 --ntasks-per-node=4 --cpus-per-task=1
#SBATCH --gres=gpu:4 --time=24:00:00
module load gnu12/12.2.0 openmpi4/4.1.5 amber/24
source /opt/shared/apps/amber/24/amber.sh

cd ${SLURM_SUBMIT_DIR}
mpirun -np 4 pmemd.cuda.MPI -ng 4 -groupfile groupfile -rem 3 -remlog rem.log -remtype rem.type
```

**For 8-replica T-REMD:** change to `--ntasks=8 --gres=gpu:8` and `-np 8 -ng 8 -rem 1`.

**Common failure modes:**
- Odd replicas → silent fail (empty mdouts). Use even count.
- `srun` → MPI_Init failure. Use mpirun.
- `-rem` in groupfile → ignored. Cmd line only.
- numexchg without `-rem` flag → `NUMEXCHG requires parallel build` error.

**T-REMD explicit solvent (studies on RNA REMD):**
- 8 replicas 300-400K + ~5000 waters → 0.4-2.3% acceptance (target 20-30%)
- Solvent heat capacity dominates ΔE → sampling NOT enhanced
- **Solution:** use REST2 (4 replicas sufficient, 34-53% acceptance)

**Throughput:** ~75 ns/day per replica on RTX A6000.

---


| Pair | λ_i → λ_j | Accept |
|------|-----------|--------|
| (1,2) | 1.00 → 0.75 | 34.4% |
| (2,3) | 0.75 → 0.56 | 41.5% |
| (3,4) | 0.56 → 0.42 | 52.6% |

Physical replica (λ=1.0) populated αL basin (10.5%, 1048/10000 frames) — first method in 39-study series to cross φ=0 barrier in ≤10 ns.

## Domain Limits

- **Charge-only** = approximate REST2. Full REST2 also scales LJ ε by λ (requires per-atom-type `addLJType` in parmed). Expected ~5-10% more acceptance. Future: implement per-type LJ loop.
- **Larger systems (>200 residues):** need solute mask restriction in parmed pipeline. Straightforward extension.

---

## References

- REST2: Wang et al. JPCB 2011, DOI:10.1021/jp204430w
- Charge-only variant: Bussi, Mol Phys 2013
- T-REMD: Sugita & Okamoto 1999
- Ladder spacing: Patriksson & van der Spoel 2008
- Amber 24 manual: Chapter 25.3

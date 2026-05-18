#!/usr/bin/env python3
"""
Trp-cage REMD analysis driver.

Standard T-REMD (rem=1): each remd_NN.nc is the ensemble at fixed temperature T0_NN.
For each replica, run cpptraj to compute RMSD vs 1L2Y ref, Q (native contacts), Rg, E2E.
"""
import math, os, subprocess, sys

T_MIN, T_MAX, N_REP = 270.0, 600.0, 16
temps = [T_MIN * math.exp(i * math.log(T_MAX / T_MIN) / (N_REP - 1)) for i in range(N_REP)]
temps[-1] = T_MAX

STUDY = "/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding"
PRMTOP = "/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop"
REF_PDB = "/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/raw_pdbs/1L2Y_model1.pdb"
TRAJ_DIR = f"{STUDY}/simulations/remd_prod"
OUT = f"{STUDY}/analysis/by_temp"

os.makedirs(OUT, exist_ok=True)

# Write one cpptraj input per replica
for i, T in enumerate(temps):
    cpp = f"""\
parm {PRMTOP} [solv]
parm {REF_PDB} [ref]
reference {REF_PDB} parm [ref] [REF1L2Y]
trajin {TRAJ_DIR}/remd_{i:02d}.nc parm [solv]
strip :WAT,Na+,Cl-
autoimage

rms RMSD ref [REF1L2Y] @CA,C,N out {OUT}/rmsd_{i:02d}.dat mass
radgyr Rg @CA,C,N,O,CB out {OUT}/rg_{i:02d}.dat
nativecontacts :1-20&!@H= name Q distance 7.0 reference out {OUT}/q_{i:02d}.dat
distance E2E :1@CA :20@CA out {OUT}/e2e_{i:02d}.dat

run
"""
    with open(f"{OUT}/cpptraj_{i:02d}.in", "w") as f:
        f.write(cpp)

# Write SLURM script — array job, one task per replica
slurm = f"""\
#!/bin/bash
#SBATCH --job-name=remd_cpptraj
#SBATCH --partition=defq
#SBATCH --array=0-15
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=01:00:00
#SBATCH --output={STUDY}/logs/cpptraj_%a.out
#SBATCH --error={STUDY}/logs/cpptraj_%a.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

IDX=$(printf "%02d" ${{SLURM_ARRAY_TASK_ID}})
cd {OUT}
cpptraj -i {OUT}/cpptraj_${{IDX}}.in > {OUT}/cpptraj_${{IDX}}.log 2>&1
echo "cpptraj replica ${{IDX}} done. Exit: $?"
"""
with open(f"{OUT}/run_cpptraj.sh", "w") as f:
    f.write(slurm)

print(f"Wrote {N_REP} cpptraj.in files and SLURM array script")
print(f"Submit: sbatch {OUT}/run_cpptraj.sh")

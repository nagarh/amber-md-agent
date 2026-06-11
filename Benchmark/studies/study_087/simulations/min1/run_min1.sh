#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/min1
#SBATCH --job-name=min1_087
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=16
#SBATCH --time=06:00:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/min1_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/min1_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/min1

# CPU minimization (pmemd.MPI) — manual p.235: packmol-memgen clashes must be relaxed on
# CPU first (GPU "illegal memory access" on extreme forces). Restrain protein backbone,
# let lipid tails / water relax out the close contacts.
PRM=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system/ompf_membrane.prmtop
INP=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system/ompf_membrane_centered.inpcrd

mpirun -np 16 pmemd.MPI -O -i min1.mdin -p $PRM -c $INP -ref $INP \
   -o min1.mdout -r min1.rst7 -inf min1.mdinfo
echo "exit: $?"

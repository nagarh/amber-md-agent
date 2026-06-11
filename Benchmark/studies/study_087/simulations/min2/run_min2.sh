#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/min2
#SBATCH --job-name=min2_087
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=16
#SBATCH --time=06:00:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/min2_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/min2_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/min2

# CPU full minimization continuing from min1 (weak backbone restraint). After this the
# forces are tame enough for the GPU (heat onward runs on pmemd.cuda).
PRM=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system/ompf_membrane.prmtop
mpirun -np 16 pmemd.MPI -O -i min2.mdin -p $PRM \
   -c ../min1/min1.rst7 -ref ../min1/min1.rst7 \
   -o min2.mdout -r min2.rst7 -inf min2.mdinfo
echo "exit: $?"

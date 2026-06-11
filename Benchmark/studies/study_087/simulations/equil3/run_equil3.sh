#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/equil3
#SBATCH --job-name=equil3_087
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=08:00:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/equil3_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/equil3_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/equil3
pmemd.cuda -O -i /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/equil3/equil3.mdin -p /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system/ompf_membrane.prmtop -c /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/equil2/equil2.rst7  \
   -o equil3.mdout -r equil3.rst7 -x equil3.nc -inf equil3.mdinfo
echo "exit: $?"

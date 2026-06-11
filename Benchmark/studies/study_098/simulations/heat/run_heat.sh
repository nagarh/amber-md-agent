#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --job-name=heat_098
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/heat_098_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/heat_098_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

S=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098
cd $S/simulations/heat
pmemd.cuda -O -i heat.mdin -p $S/system/system.prmtop -c $S/simulations/min2/min2.rst7 \
  -ref $S/simulations/min2/min2.rst7 -o heat.mdout -r heat.rst7 -x heat.nc -inf heat.mdinfo

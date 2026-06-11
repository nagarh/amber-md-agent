#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --job-name=equil2_098
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/equil2_098_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/equil2_098_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

S=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098
cd $S/simulations/equil2
pmemd.cuda -O -i equil2.mdin -p $S/system/system.prmtop -c $S/simulations/equil/equil.rst7 \
  -o equil2.mdout -r equil2.rst7 -x equil2.nc -inf equil2.mdinfo

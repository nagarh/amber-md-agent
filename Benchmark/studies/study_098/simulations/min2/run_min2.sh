#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=01:00:00
#SBATCH --job-name=min2_098
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/min2_098_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/min2_098_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

S=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098
cd $S/simulations/min2
pmemd.cuda -O -i min2.mdin -p $S/system/system.prmtop -c $S/simulations/min1/min1.rst7 \
  -o min2.mdout -r min2.rst7 -inf min2.mdinfo

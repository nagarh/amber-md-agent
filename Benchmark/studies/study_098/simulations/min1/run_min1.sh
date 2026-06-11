#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=01:00:00
#SBATCH --job-name=min1_098
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/min1_098_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/min1_098_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

S=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098
cd $S/simulations/min1
pmemd.cuda -O -i min1.mdin -p $S/system/system.prmtop -c $S/system/system.inpcrd \
  -ref $S/system/system.inpcrd -o min1.mdout -r min1.rst7 -inf min1.mdinfo

#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH --job-name=prod_098
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/prod_098_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098/logs/prod_098_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

S=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_098
cd $S/simulations/prod
pmemd.cuda -O -i prod.mdin -p $S/system/system.prmtop -c $S/simulations/equil2/equil2.rst7 \
  -o prod.mdout -r prod.rst7 -x prod.nc -inf prod.mdinfo

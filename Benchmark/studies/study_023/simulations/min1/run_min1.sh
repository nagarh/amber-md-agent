#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/min1
#SBATCH --job-name=min1_s023
#SBATCH --partition=defq
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:20:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/%x_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/%x_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

SYS=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/system
cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/min1

pmemd.cuda -O -i min1.mdin -o min1.mdout -p $SYS/system.prmtop -c $SYS/system.inpcrd \
  -r min1.rst7 -ref $SYS/system.inpcrd -inf min1.mdinfo
echo "MIN1_DONE exit=$?"

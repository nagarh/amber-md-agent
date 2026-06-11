#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/min2
#SBATCH --job-name=min2_s023
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
M1=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/min1
cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/min2

pmemd.cuda -O -i min2.mdin -o min2.mdout -p $SYS/system.prmtop -c $M1/min1.rst7 \
  -r min2.rst7 -inf min2.mdinfo
echo "MIN2_DONE exit=$?"

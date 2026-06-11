#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/heat
#SBATCH --job-name=heat_s023
#SBATCH --partition=defq
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/%x_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/%x_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

SYS=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/system
M2=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/min2
cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/heat

pmemd.cuda -O -i heat.mdin -o heat.mdout -p $SYS/system.prmtop -c $M2/min2.rst7 \
  -r heat.rst7 -ref $M2/min2.rst7 -x heat.nc -inf heat.mdinfo
echo "HEAT_DONE exit=$?"

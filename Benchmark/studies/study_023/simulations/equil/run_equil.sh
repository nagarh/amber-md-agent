#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/equil
#SBATCH --job-name=equil_s023
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
HT=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/heat
cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/equil

pmemd.cuda -O -i equil.mdin -o equil.mdout -p $SYS/system.prmtop -c $HT/heat.rst7 \
  -r equil.rst7 -ref $HT/heat.rst7 -x equil.nc -inf equil.mdinfo
echo "EQUIL_DONE exit=$?"

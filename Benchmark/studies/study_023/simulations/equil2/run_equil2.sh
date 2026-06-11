#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/equil2
#SBATCH --job-name=equil2_s023
#SBATCH --partition=defq
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:40:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/%x_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/%x_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

SYS=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/system
EQ=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/equil
cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/equil2

pmemd.cuda -O -i equil2.mdin -o equil2.mdout -p $SYS/system.prmtop -c $EQ/equil.rst7 \
  -r equil2.rst7 -x equil2.nc -inf equil2.mdinfo
echo "EQUIL2_DONE exit=$?"

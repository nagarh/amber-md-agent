#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/prod
#SBATCH --job-name=prod_s023
#SBATCH --partition=defq
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=24:00:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/%x_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/%x_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

SYS=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/system
E2=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/equil2
cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/simulations/prod

pmemd.cuda -O -i prod.mdin -o prod.mdout -p $SYS/system.prmtop -c $E2/equil2.rst7 \
  -r prod.rst7 -x prod.nc -inf prod.mdinfo
echo "PROD_DONE exit=$?"

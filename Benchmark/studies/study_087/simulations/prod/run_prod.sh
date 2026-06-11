#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/prod
#SBATCH --job-name=prod_087
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=72:00:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/prod_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/prod_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/prod
pmemd.cuda -O -i /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/prod/prod.mdin -p /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system/ompf_membrane.prmtop -c /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/equil3/equil3.rst7  \
   -o prod.mdout -r prod.rst7 -x prod.nc -inf prod.mdinfo
echo "exit: $?"

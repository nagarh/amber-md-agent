#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/simulations/prod
#SBATCH --job-name=prod_071
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=96:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/prod_071_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/prod_071_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/simulations/prod
pmemd.cuda -O -i prod.mdin -o prod.mdout -p ../../system/system.prmtop -c ../equil2/equil2.rst7 -r prod.rst7 -x prod.nc -inf prod.mdinfo

echo "Job finished: $(date)"

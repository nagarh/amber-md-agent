#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/simulations/equil
#SBATCH --job-name=equil_071
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=01:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/equil_071_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/equil_071_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/simulations/equil
pmemd.cuda -O -i equil.mdin -o equil.mdout -p ../../system/system.prmtop -c ../heat/heat.rst7 -r equil.rst7 -ref ../heat/heat.rst7 -x equil.nc -inf equil.mdinfo

echo "Job finished: $(date)"

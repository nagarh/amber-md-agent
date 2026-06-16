#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/simulations/heat
#SBATCH --job-name=heat_071
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=01:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/heat_071_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/heat_071_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/simulations/heat
pmemd.cuda -O -i heat.mdin -o heat.mdout -p ../../system/system.prmtop -c ../min2/min2.rst7 -r heat.rst7 -ref ../min2/min2.rst7 -x heat.nc -inf heat.mdinfo

echo "Job finished: $(date)"

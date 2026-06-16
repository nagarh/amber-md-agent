#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/simulations/min2
#SBATCH --job-name=min2_071
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --gres=gpu:1
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/min2_071_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/min2_071_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/simulations/min2
pmemd.cuda -O -i min2.mdin -o min2.mdout -p ../../system/system.prmtop -c ../min1/min1.rst7 -r min2.rst7 -inf min2.mdinfo

echo "Job finished: $(date)"

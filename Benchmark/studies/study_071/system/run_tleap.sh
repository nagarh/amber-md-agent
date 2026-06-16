#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/system
#SBATCH --job-name=tleap_071
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/tleap_071_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/logs/tleap_071_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_071/system && tleap -f tleap.in > tleap.log 2>&1

echo "Job finished: $(date)"

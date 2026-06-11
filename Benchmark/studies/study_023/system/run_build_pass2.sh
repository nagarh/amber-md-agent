#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/system
#SBATCH --job-name=build_p2_s023
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:20:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/build_p2_s023_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/logs/build_p2_s023_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/system
tleap -f /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/system/build_pass2.in > /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/system/tleap_pass2.out 2>&1
echo "BUILD_PASS2_DONE"

echo "Job finished: $(date)"

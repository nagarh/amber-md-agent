#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/CDK2_apo/system
#SBATCH --job-name=CDK2_tleap
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=00:30:00
#SBATCH --output=CDK2_tleap_%j.out
#SBATCH --error=CDK2_tleap_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh && tleap -f studies/CDK2_apo/system/tleap.in > studies/CDK2_apo/system/leap.log 2>&1

echo "Job finished: $(date)"

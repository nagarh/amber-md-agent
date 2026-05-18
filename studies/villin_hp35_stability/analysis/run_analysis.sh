#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/analysis
#SBATCH --job-name=analysis_villin
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --output=analysis_villin_%j.out
#SBATCH --error=analysis_villin_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cpptraj -i /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/analysis/analyze.in > /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/analysis/cpptraj.log 2>&1

echo "Job finished: $(date)"

#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system
#SBATCH --job-name=tleap_villin
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --output=tleap_villin_%j.out
#SBATCH --error=tleap_villin_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh
cd /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system
tleap -f tleap.in > leap.log 2>&1

echo "Job finished: $(date)"

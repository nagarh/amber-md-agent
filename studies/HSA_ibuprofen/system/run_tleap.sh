#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system
#SBATCH --job-name=tleap_HSA
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --output=tleap_HSA_%j.out
#SBATCH --error=tleap_HSA_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system && tleap -f tleap.in > tleap.log 2>&1 && echo TLEAP_DONE

echo "Job finished: $(date)"

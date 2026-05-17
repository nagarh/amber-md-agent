#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/logs
#SBATCH --job-name=p4a_help2
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:02:00
#SBATCH --output=p4a_help2_%j.out
#SBATCH --error=p4a_help2_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

module load gnu12/12.2.0
 module load amber/24
 source /opt/shared/apps/amber/24/amber.sh
 pdb4amber --help 2>&1 | head -80
 echo END

echo "Job finished: $(date)"

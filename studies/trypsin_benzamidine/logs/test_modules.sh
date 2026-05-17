#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/logs
#SBATCH --job-name=tb_modtest
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:05:00
#SBATCH --output=tb_modtest_%j.out
#SBATCH --error=tb_modtest_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

echo HOST=$(hostname)
 module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh && which tleap antechamber pmemd.cuda cpptraj pdb4amber parmchk2 sqm
 echo DONE

echo "Job finished: $(date)"

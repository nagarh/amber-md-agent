#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/logs
#SBATCH --job-name=tb_modtest2
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:05:00
#SBATCH --output=tb_modtest2_%j.out
#SBATCH --error=tb_modtest2_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

set -x
 module avail amber 2>&1 | head -20
 module load gnu12/12.2.0 2>&1
 module load amber/24 2>&1
 module list 2>&1
 ls -la /opt/shared/apps/amber/24/ 2>&1 | head
 source /opt/shared/apps/amber/24/amber.sh 2>&1
 echo PATH=$PATH
 echo AMBERHOME=$AMBERHOME
 ls $AMBERHOME/bin/ 2>&1 | head
 which tleap antechamber pmemd.cuda cpptraj pdb4amber parmchk2 sqm 2>&1

echo "Job finished: $(date)"

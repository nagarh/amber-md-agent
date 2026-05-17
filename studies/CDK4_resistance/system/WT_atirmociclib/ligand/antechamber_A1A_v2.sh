#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/system/WT_atirmociclib/ligand
#SBATCH --job-name=antechamber_A1A
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=2:00:00
#SBATCH --output=antechamber_A1A_%j.out
#SBATCH --error=antechamber_A1A_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/system/WT_atirmociclib/ligand && antechamber -i A1A.pdb -fi pdb -o A1A.mol2 -fo mol2 -c bcc -nc 0 -rn A1A -at gaff2 && parmchk2 -i A1A.mol2 -f mol2 -o A1A.frcmod -s gaff2

echo "Job finished: $(date)"

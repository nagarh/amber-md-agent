#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/system/WT_abemaciclib/ligand
#SBATCH --job-name=antechamber_6ZV
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=2:00:00
#SBATCH --output=antechamber_6ZV_%j.out
#SBATCH --error=antechamber_6ZV_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/system/WT_abemaciclib/ligand && antechamber -i 6ZV_H.pdb -fi pdb -o 6ZV.mol2 -fo mol2 -c bcc -nc 0 -rn 6ZV -at gaff2 && parmchk2 -i 6ZV.mol2 -f mol2 -o 6ZV.frcmod -s gaff2

echo "Job finished: $(date)"

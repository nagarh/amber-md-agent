#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system
#SBATCH --job-name=sti_antechamber
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=01:00:00
#SBATCH --output=sti_antechamber_%j.out
#SBATCH --error=sti_antechamber_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

antechamber -i ligand_ready.sdf -fi sdf -o ligand.mol2 -fo mol2 -c bcc -at gaff2 -nc 0 && parmchk2 -i ligand.mol2 -f mol2 -o ligand.frcmod && echo ANTECHAMBER_DONE

echo "Job finished: $(date)"

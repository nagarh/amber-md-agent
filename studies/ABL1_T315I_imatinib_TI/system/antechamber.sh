#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/system
#SBATCH --job-name=antechamber_sti
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=antechamber_sti_%j.out
#SBATCH --error=antechamber_sti_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/system && antechamber -i imatinib_ready.sdf -fi sdf -o imatinib.mol2 -fo mol2 -c bcc -at gaff2 -nc 0 && parmchk2 -i imatinib.mol2 -f mol2 -o imatinib.frcmod

echo "Job finished: $(date)"

#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system
#SBATCH --job-name=antechamber_HSA
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=01:00:00
#SBATCH --output=antechamber_HSA_%j.out
#SBATCH --error=antechamber_HSA_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system && antechamber -i ibp_A2001_ready.sdf -fi sdf -o ibp1.mol2 -fo mol2 -c bcc -at gaff2 -nc 0 > antechamber_A2001.log 2>&1 && antechamber -i ibp_A2002_ready.sdf -fi sdf -o ibp2.mol2 -fo mol2 -c bcc -at gaff2 -nc 0 > antechamber_A2002.log 2>&1 && parmchk2 -i ibp1.mol2 -f mol2 -o ibp.frcmod -s 2 > parmchk2.log 2>&1 && echo ANTECHAMBER_DONE

echo "Job finished: $(date)"

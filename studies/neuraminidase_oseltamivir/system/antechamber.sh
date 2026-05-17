#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system
#SBATCH --job-name=antechamber_G39
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=02:00:00
#SBATCH --output=antechamber_G39_%j.out
#SBATCH --error=antechamber_G39_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system
antechamber -i ligand_ready.sdf -fi sdf -o ligand.mol2 -fo mol2 -c bcc -at gaff2 -nc 0 2>&1 | tee antechamber.log
parmchk2 -i ligand.mol2 -f mol2 -o ligand.frcmod 2>&1 | tee parmchk2.log
echo DONE

echo "Job finished: $(date)"

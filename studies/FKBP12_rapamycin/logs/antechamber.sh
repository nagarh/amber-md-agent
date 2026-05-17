#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system
#SBATCH --job-name=antechamber_rap
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=02:00:00
#SBATCH --output=antechamber_rap_%j.out
#SBATCH --error=antechamber_rap_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

antechamber -i ligand_ready.sdf -fi sdf -o rap.mol2 -fo mol2 -c bcc -at gaff2 -nc 0 -pf y && parmchk2 -i rap.mol2 -f mol2 -o rap.frcmod

echo "Job finished: $(date)"

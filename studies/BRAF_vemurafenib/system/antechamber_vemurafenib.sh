#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/BRAF_vemurafenib/system
#SBATCH --job-name=antechamber_vemurafenib
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=antechamber_vemurafenib_%j.out
#SBATCH --error=antechamber_vemurafenib_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

cd /home/hn533621/Portfolio/amber-md-agent/studies/BRAF_vemurafenib/system && antechamber -i /home/hn533621/Portfolio/amber-md-agent/studies/BRAF_vemurafenib/raw_pdbs/vemurafenib_aligned.sdf -fi sdf -o vemurafenib.mol2 -fo mol2 -c bcc -at gaff2 -nc 0 && parmchk2 -i vemurafenib.mol2 -f mol2 -o vemurafenib.frcmod && echo 'Antechamber DONE'

echo "Job finished: $(date)"

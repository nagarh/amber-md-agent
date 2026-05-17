#!/bin/bash
#SBATCH --job-name=antechamber_RIT
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=antechamber_RIT_%j.out
#SBATCH --error=antechamber_RIT_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"

cd /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system

echo "Running antechamber with increased SCF cycles..."
antechamber -i ritonavir.pdb -fi pdb \
            -o ritonavir.mol2 -fo mol2 \
            -at gaff2 -c bcc -nc 0 -rn RIT \
            -ek "scfconv=1.0d-8,maxcyc=2000,ndiis_attempts=700"

if [ $? -ne 0 ]; then
    echo "antechamber failed — check sqm.out"
    exit 1
fi

echo "Checking total charge in mol2..."
grep "MOLECULE" -A4 ritonavir.mol2

echo "Running parmchk2..."
parmchk2 -i ritonavir.mol2 -f mol2 -o ritonavir.frcmod -s gaff2

echo "Checking frcmod for missing parameters..."
grep "ATTN" ritonavir.frcmod || echo "No ATTN flags — parameters complete"

echo "Job finished: $(date)"

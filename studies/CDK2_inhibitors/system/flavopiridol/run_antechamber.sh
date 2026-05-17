#!/bin/bash
#SBATCH --job-name=antechamber_F9Z
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=antechamber_F9Z_%j.out
#SBATCH --error=antechamber_F9Z_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"

cd /home/hn533621/Portfolio/amber-md-agent/studies/CDK2_inhibitors/system/flavopiridol

echo "Running antechamber for flavopiridol (F9Z, charge=0)..."
antechamber -i F9Z_aligned.sdf -fi sdf \
            -o F9Z.mol2 -fo mol2 \
            -at gaff2 -c bcc -nc 0 -rn F9Z \
            -s 2

if [ $? -ne 0 ]; then
    echo "antechamber failed — check sqm.out"
    exit 1
fi

echo "Checking total charge in mol2..."
grep "MOLECULE" -A4 F9Z.mol2

echo "Running parmchk2..."
parmchk2 -i F9Z.mol2 -f mol2 -o F9Z.frcmod -s gaff2

echo "Checking frcmod for missing parameters..."
grep "ATTN" F9Z.frcmod || echo "No ATTN flags — parameters complete"

echo "Job finished: $(date)"

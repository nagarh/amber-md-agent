#!/bin/bash
#SBATCH --job-name=antechamber_1QK
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=antechamber_1QK_%j.out
#SBATCH --error=antechamber_1QK_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"

cd /home/hn533621/Portfolio/amber-md-agent/studies/CDK2_inhibitors/system/dinaciclib

echo "Running antechamber for dinaciclib (1QK, charge=0)..."
antechamber -i 1QK_aligned.sdf -fi sdf \
            -o 1QK.mol2 -fo mol2 \
            -at gaff2 -c bcc -nc 0 -rn 1QK \
            -s 2

if [ $? -ne 0 ]; then
    echo "antechamber failed — check sqm.out"
    exit 1
fi

echo "Checking total charge in mol2..."
grep "MOLECULE" -A4 1QK.mol2

echo "Running parmchk2..."
parmchk2 -i 1QK.mol2 -f mol2 -o 1QK.frcmod -s gaff2

echo "Checking frcmod for missing parameters..."
grep "ATTN" 1QK.frcmod || echo "No ATTN flags — parameters complete"

echo "Job finished: $(date)"

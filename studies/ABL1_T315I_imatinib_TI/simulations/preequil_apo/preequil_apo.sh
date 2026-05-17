#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/simulations/preequil_apo
#SBATCH --job-name=preequil_apo_abl1ti
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=04:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=preequil_apo_abl1ti_%j.out
#SBATCH --error=preequil_apo_abl1ti_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/simulations/preequil_apo
module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh
PRMTOP=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/system/ti_merged_apo.prmtop
INPCRD=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/system/ti_merged_apo.inpcrd
pmemd.cuda -O -i preequil_min1.mdin -o min1.mdout -p $PRMTOP -c $INPCRD -r min1.rst7 -ref $INPCRD
pmemd.cuda -O -i preequil_min2.mdin -o min2.mdout -p $PRMTOP -c min1.rst7 -r min2.rst7
pmemd.cuda -O -i preequil_heat.mdin -o heat.mdout -p $PRMTOP -c min2.rst7 -r heat.rst7 -x heat.nc -ref min2.rst7
pmemd.cuda -O -i preequil_equil.mdin -o equil.mdout -p $PRMTOP -c heat.rst7 -r equil.rst7 -x equil.nc -ref heat.rst7

echo "Job finished: $(date)"

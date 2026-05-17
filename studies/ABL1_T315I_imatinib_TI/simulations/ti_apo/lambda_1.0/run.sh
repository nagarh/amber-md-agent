#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/simulations/ti_apo/lambda_1.0
#SBATCH --job-name=ti_ti_apo_l1.0_rerun
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=04:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=ti_ti_apo_l1.0_rerun_%j.out
#SBATCH --error=ti_ti_apo_l1.0_rerun_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/simulations/ti_apo/lambda_1.0
PRMTOP=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/system/ti_merged_apo.prmtop
REFCRD=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/simulations/ti_apo/lambda_0.9/equil.rst7
pmemd.cuda -O -i equil.mdin -o equil.mdout -p $PRMTOP -c $REFCRD -r equil.rst7 -x equil.nc
pmemd.cuda -O -i prod.mdin -o prod.mdout -p $PRMTOP -c equil.rst7 -r prod.rst7 -x prod.nc

echo "Job finished: $(date)"

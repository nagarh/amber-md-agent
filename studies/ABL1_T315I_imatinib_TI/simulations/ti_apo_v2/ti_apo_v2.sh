#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI/simulations/ti_apo_v2
#SBATCH --job-name=ti_apo_v2
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=168:00:00
#SBATCH --gres=gpu:1
#SBATCH --array=0-10
#SBATCH --output=ti_apo_v2_%A_%a.out
#SBATCH --error=ti_apo_v2_%A_%a.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Array task $SLURM_ARRAY_TASK_ID started: $(date)"

LAMBDA=$(python3 -c "print(f'{${SLURM_ARRAY_TASK_ID}*0.1:.1f}')")
echo "Lambda = $LAMBDA"

STUDY=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI
cd ${STUDY}/simulations/ti_apo_v2/lambda_${LAMBDA}
PRMTOP=${STUDY}/system/ti_merged_apo.prmtop
REFCRD=${STUDY}/simulations/preequil_apo/equil.rst7

pmemd.cuda -O -i equil.mdin -o equil.mdout -p ${PRMTOP} -c ${REFCRD} -r equil.rst7 -x equil.nc
pmemd.cuda -O -i prod.mdin -o prod.mdout -p ${PRMTOP} -c equil.rst7 -r prod.rst7 -x prod.nc

echo "Array task $SLURM_ARRAY_TASK_ID finished: $(date)"

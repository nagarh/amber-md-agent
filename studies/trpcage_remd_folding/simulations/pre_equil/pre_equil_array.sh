#!/bin/bash
#SBATCH --job-name=remd_preequil
#SBATCH --partition=defq
#SBATCH --array=0-15
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --time=00:30:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/preequil_%a.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/preequil_%a.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

IDX=$(printf "%02d" ${SLURM_ARRAY_TASK_ID})

PRMTOP=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop
START_RST=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/simulations/equil/equil2.rst7
WORK=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/pre_equil

cd ${WORK}

pmemd.cuda -O \
  -i preq_${IDX}.mdin \
  -p ${PRMTOP} \
  -c ${START_RST} \
  -o preq_${IDX}.mdout \
  -r preq_${IDX}.rst7 \
  -inf preq_${IDX}.mdinfo

echo "Replica ${IDX} pre-equil complete. Exit: $?"

#!/bin/bash
#SBATCH --job-name=remd_trpcage
#SBATCH --partition=defq
#SBATCH --nodes=2
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=8
#SBATCH --gres=gpu:8
#SBATCH --time=12:00:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/remd_prod.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/remd_prod.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

REMD_DIR=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/remd_prod

cd ${REMD_DIR}

nvidia-smi -L
echo "=== REMD 16 replicas, 2 nodes × 8 GPUs ==="

srun --mpi=pmix -n 16 pmemd.cuda.MPI \
  -ng 16 \
  -groupfile ${REMD_DIR}/remd_group.in \
  -rem 1 \
  -remlog ${REMD_DIR}/remd.log

echo "REMD production complete. Exit: $?"

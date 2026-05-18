#!/bin/bash
#SBATCH --job-name=remd_cpptraj
#SBATCH --partition=defq
#SBATCH --array=0-15
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=01:00:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/cpptraj_%a.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/cpptraj_%a.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

IDX=$(printf "%02d" ${SLURM_ARRAY_TASK_ID})
cd /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/analysis/by_temp
cpptraj -i /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/analysis/by_temp/cpptraj_${IDX}.in > /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/analysis/by_temp/cpptraj_${IDX}.log 2>&1
echo "cpptraj replica ${IDX} done. Exit: $?"

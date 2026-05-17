#!/bin/bash
#SBATCH --job-name=HIV1PR_us
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=168:00:00
#SBATCH --gres=gpu:1
#SBATCH --array=0-49
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/windows/slurm_%A_%a.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/windows/slurm_%A_%a.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

# Map array index to window directory
WDIRS=($(ls -d /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/windows/w*/ | sort))
WDIR=${WDIRS[$SLURM_ARRAY_TASK_ID]}

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Window dir: $WDIR"

cd $WDIR

pmemd.cuda -O \
  -i us.mdin \
  -o us.mdout \
  -p /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system/system.prmtop \
  -c start.rst7 \
  -r us.rst7 \
  -x us.nc \
  -ref start.rst7

echo "Window complete: $(date)"

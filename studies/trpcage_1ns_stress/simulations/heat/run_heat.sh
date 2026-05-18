#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/simulations/heat
#SBATCH --job-name=heat_trpcage
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=01:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=heat_trpcage_%j.out
#SBATCH --error=heat_trpcage_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh
cd /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/simulations/heat
pmemd.cuda -O \
  -i heat.mdin \
  -o heat.mdout \
  -p /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop \
  -c /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/simulations/min2/min2.rst7 \
  -r heat.rst7 \
  -x heat.nc \
  -ref /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.inpcrd

echo "Job finished: $(date)"

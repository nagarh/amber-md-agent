#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/simulations/prod
#SBATCH --job-name=prod_trpcage
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=prod_trpcage_%j.out
#SBATCH --error=prod_trpcage_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh
cd /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/simulations/prod
pmemd.cuda -O \
  -i prod.mdin \
  -o prod.mdout \
  -p /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop \
  -c /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/simulations/equil/equil2.rst7 \
  -r prod.rst7 \
  -x prod.nc

echo "Job finished: $(date)"

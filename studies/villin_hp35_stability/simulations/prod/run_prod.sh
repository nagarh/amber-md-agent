#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/prod
#SBATCH --job-name=prod_villin
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=prod_villin_%j.out
#SBATCH --error=prod_villin_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O \
  -i prod.mdin \
  -o prod.mdout \
  -p /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system/system.prmtop \
  -c /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/equil2/equil2.rst7 \
  -r prod.rst7 \
  -x prod.nc

echo "Job finished: $(date)"

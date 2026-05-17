#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/prod
#SBATCH --job-name=prod_neuraminidase
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=48:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=prod_neuraminidase_%j.out
#SBATCH --error=prod_neuraminidase_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/prod && pmemd.cuda -O -i prod.mdin -o prod.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/equil/equil.rst7 -r prod.rst7 -x prod.nc

echo "Job finished: $(date)"

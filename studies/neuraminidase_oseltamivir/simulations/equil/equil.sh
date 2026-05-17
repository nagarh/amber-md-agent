#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/equil
#SBATCH --job-name=equil_neuraminidase
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=08:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=equil_neuraminidase_%j.out
#SBATCH --error=equil_neuraminidase_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/equil && pmemd.cuda -O -i equil.mdin -o equil.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/heat/heat.rst7 -r equil.rst7 -x equil.nc -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system/system.inpcrd

echo "Job finished: $(date)"

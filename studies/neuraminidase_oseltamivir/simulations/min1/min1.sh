#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/min1
#SBATCH --job-name=min1_neuraminidase
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=04:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=min1_neuraminidase_%j.out
#SBATCH --error=min1_neuraminidase_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/min1
pmemd.cuda -O -i min1.mdin -o min1.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system/system.inpcrd -r min1.rst7 -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system/system.inpcrd

echo "Job finished: $(date)"

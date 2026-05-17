#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/min2
#SBATCH --job-name=min2_neuraminidase
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=04:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=min2_neuraminidase_%j.out
#SBATCH --error=min2_neuraminidase_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/min2 && pmemd.cuda -O -i min2.mdin -o min2.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/neuraminidase_oseltamivir/simulations/min1/min1.rst7 -r min2.rst7

echo "Job finished: $(date)"

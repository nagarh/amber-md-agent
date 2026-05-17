#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/min1
#SBATCH --job-name=min1_villin
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --gres=gpu:1
#SBATCH --output=min1_villin_%j.out
#SBATCH --error=min1_villin_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh
cd /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/min1
PRMTOP=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system/system.prmtop
INPCRD=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system/system.inpcrd
pmemd.cuda -O -i min1.mdin -o min1.mdout -p $PRMTOP -c $INPCRD -r min1.rst7 -ref $INPCRD

echo "Job finished: $(date)"

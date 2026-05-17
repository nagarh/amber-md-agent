#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/min2
#SBATCH --job-name=min2_villin
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --gres=gpu:1
#SBATCH --output=min2_villin_%j.out
#SBATCH --error=min2_villin_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh
cd /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/min2
PRMTOP=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system/system.prmtop
MIN1RST=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/min1/min1.rst7
pmemd.cuda -O -i min2.mdin -o min2.mdout -p $PRMTOP -c $MIN1RST -r min2.rst7

echo "Job finished: $(date)"

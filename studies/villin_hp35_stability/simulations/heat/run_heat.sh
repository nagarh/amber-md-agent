#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/heat
#SBATCH --job-name=heat_villin
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --gres=gpu:1
#SBATCH --output=heat_villin_%j.out
#SBATCH --error=heat_villin_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh
cd /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/heat
PRMTOP=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system/system.prmtop
INPCRD=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system/system.inpcrd
MIN2RST=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/min2/min2.rst7
pmemd.cuda -O -i heat.mdin -o heat.mdout -p $PRMTOP -c $MIN2RST -r heat.rst7 -ref $INPCRD -x heat.nc

echo "Job finished: $(date)"

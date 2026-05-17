#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/equil2
#SBATCH --job-name=equil2_villin
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=01:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=equil2_villin_%j.out
#SBATCH --error=equil2_villin_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh
cd /home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/equil2
PRMTOP=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system/system.prmtop
INPCRD=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/system/system.inpcrd
BURST_RST=/home/hn533621/Portfolio/amber-md-agent/studies/villin_hp35_stability/simulations/burst/burst_final.rst7
pmemd.cuda -O -i equil2.mdin -o equil2.mdout -p $PRMTOP -c $BURST_RST -r equil2.rst7 -ref $INPCRD -x equil2.nc

echo "Job finished: $(date)"

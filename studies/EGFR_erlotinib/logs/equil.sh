#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/equil
#SBATCH --job-name=egfr_equil
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=02:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=egfr_equil_%j.out
#SBATCH --error=egfr_equil_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/mdin/equil.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/equil/equil.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/heat/heat.rst7 -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/equil/equil.rst7 -x /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/equil/equil.nc -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system/system.inpcrd

echo "Job finished: $(date)"

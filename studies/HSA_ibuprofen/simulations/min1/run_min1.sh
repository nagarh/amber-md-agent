#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/min1
#SBATCH --job-name=min1_HSA
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --gres=gpu:1
#SBATCH --output=min1_HSA_%j.out
#SBATCH --error=min1_HSA_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/min1/min1.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/min1/min1.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system/system.inpcrd -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/min1/min1.rst7 -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system/system.inpcrd && echo MIN1_DONE

echo "Job finished: $(date)"

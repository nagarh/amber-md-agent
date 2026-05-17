#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/heat
#SBATCH --job-name=heat_HSA
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=01:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=heat_HSA_%j.out
#SBATCH --error=heat_HSA_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/heat/heat.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/heat/heat.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/min2/min2.rst7 -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/heat/heat.rst7 -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/min2/min2.rst7 && echo HEAT_DONE

echo "Job finished: $(date)"

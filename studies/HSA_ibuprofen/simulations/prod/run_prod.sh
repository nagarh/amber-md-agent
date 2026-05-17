#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod
#SBATCH --job-name=prod_HSA
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=72:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=prod_HSA_%j.out
#SBATCH --error=prod_HSA_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod/prod.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod/prod.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/equil2.rst7 -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod/prod.rst7 -x /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod/prod.nc && echo PROD_DONE

echo "Job finished: $(date)"

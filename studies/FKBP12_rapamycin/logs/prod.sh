#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/prod
#SBATCH --job-name=fkbp12_prod
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=48:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=fkbp12_prod_%j.out
#SBATCH --error=fkbp12_prod_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/prod/prod.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/prod/prod.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system/com_solvated.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/equil/equil.rst7 -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/prod/prod.rst7 -x /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/prod/prod.nc

echo "Job finished: $(date)"

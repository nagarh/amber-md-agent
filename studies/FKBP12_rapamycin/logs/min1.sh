#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/min1
#SBATCH --job-name=fkbp12_min1
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=01:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=fkbp12_min1_%j.out
#SBATCH --error=fkbp12_min1_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/min1/min1.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/min1/min1.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system/com_solvated.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system/com_solvated.inpcrd -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/min1/min1.rst7 -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system/com_solvated.inpcrd

echo "Job finished: $(date)"

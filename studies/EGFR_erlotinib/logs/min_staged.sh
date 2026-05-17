#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min
#SBATCH --job-name=egfr_min3
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=04:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=egfr_min3_%j.out
#SBATCH --error=egfr_min3_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/mdin/min1.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min/min1.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system/system.inpcrd -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min/min1.rst7 -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system/system.inpcrd && pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/mdin/min2.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min/min2.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min/min1.rst7 -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min/min2.rst7 -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system/system.inpcrd && pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/mdin/min3.mdin -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min/min3.mdout -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min/min2.rst7 -r /home/hn533621/Portfolio/amber-md-agent-improvements/studies/EGFR_erlotinib/simulations/min/min3.rst7

echo "Job finished: $(date)"

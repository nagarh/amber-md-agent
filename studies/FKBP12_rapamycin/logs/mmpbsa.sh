#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/analysis
#SBATCH --job-name=fkbp12_mmpbsa
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=04:00:00
#SBATCH --output=fkbp12_mmpbsa_%j.out
#SBATCH --error=fkbp12_mmpbsa_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

MMPBSA.py -O     -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/analysis/mmpbsa.in     -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/analysis/FINAL_RESULTS_MMPBSA.dat     -do /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/analysis/FINAL_DECOMP_MMPBSA.dat     -sp /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system/com_solvated.prmtop     -cp /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system/com.prmtop     -rp /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system/rec.prmtop     -lp /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/system/lig.prmtop     -y /home/hn533621/Portfolio/amber-md-agent-improvements/studies/FKBP12_rapamycin/simulations/prod/prod.nc

echo "Job finished: $(date)"

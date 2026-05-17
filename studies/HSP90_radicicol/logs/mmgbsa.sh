#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/analysis
#SBATCH --job-name=HSP90_MMGBSA
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=04:00:00
#SBATCH --output=HSP90_MMGBSA_%j.out
#SBATCH --error=HSP90_MMGBSA_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"

set -e
module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/analysis
MMPBSA.py -O   -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/analysis/mmgbsa.in   -o /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/analysis/mmgbsa_results.dat   -sp /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/system/system.prmtop   -cp /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/analysis/complex.prmtop   -rp /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/analysis/receptor.prmtop   -lp /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/analysis/ligand.prmtop   -y  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/prod/prod.nc
echo 'MMGBSA_COMPLETE'

echo "Job finished: $(date)"

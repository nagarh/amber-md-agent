#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol
#SBATCH --job-name=HSP90_RDC_prod
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=24:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=HSP90_RDC_prod_%j.out
#SBATCH --error=HSP90_RDC_prod_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

set -e
module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh

PRMTOP=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/system/system.prmtop

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/prod
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/prod.mdin -o prod.mdout -p ${PRMTOP} -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/equil.rst7 -r prod.rst7 -x prod.nc
echo 'PRODUCTION_COMPLETE'

echo "Job finished: $(date)"

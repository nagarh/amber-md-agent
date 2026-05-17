#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol
#SBATCH --job-name=HSP90_RDC_heq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=12:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=HSP90_RDC_heq_%j.out
#SBATCH --error=HSP90_RDC_heq_%j.err

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

# heat: 0→300K, 1 ns
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/heat
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/heat.mdin -o heat.mdout -p ${PRMTOP} -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/min2/min2.rst7 -r heat.rst7 -x heat.nc -ref /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/system/system.inpcrd
echo 'heat done'

# equil: 5 ns NTP, Berendsen
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/equil.mdin -o equil.mdout -p ${PRMTOP} -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/heat/heat.rst7 -r equil.rst7 -x equil.nc
echo 'equil done'
echo 'HEAT_EQUIL_COMPLETE'

echo "Job finished: $(date)"

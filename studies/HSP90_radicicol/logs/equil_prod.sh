#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol
#SBATCH --job-name=HSP90_RDC_eqprod
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=06:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=HSP90_RDC_eqprod_%j.out
#SBATCH --error=HSP90_RDC_eqprod_%j.err

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

# equil: 50 ps NTP, Berendsen taup=0.5
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/equil.mdin -o equil.mdout -p ${PRMTOP} -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/heat/heat.rst7 -r equil.rst7 -x equil.nc
echo 'equil done'

# production: 200 ps NTP, MC barostat
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/prod
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/prod.mdin -o prod.mdout -p ${PRMTOP} -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/equil.rst7 -r prod.rst7 -x prod.nc
echo 'prod done'
echo 'EQUIL_PROD_COMPLETE'

echo "Job finished: $(date)"

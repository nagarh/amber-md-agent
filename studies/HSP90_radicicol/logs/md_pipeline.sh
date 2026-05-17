#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol
#SBATCH --job-name=HSP90_RDC_md
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=48:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=HSP90_RDC_md_%j.out
#SBATCH --error=HSP90_RDC_md_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

module load gnu12/12.2.0 && module load amber/24 && source /opt/shared/apps/amber/24/amber.sh

PRMTOP=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/system/system.prmtop
INPCRD=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/system/system.inpcrd

# min1: H-only minimization
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/min1
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/min1.mdin -o min1.mdout -p ${PRMTOP} -c ${INPCRD} -r min1.rst7 -ref ${INPCRD}
echo 'min1 done'

# min2: full minimization
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/min2
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/min2.mdin -o min2.mdout -p ${PRMTOP} -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/min1/min1.rst7 -r min2.rst7
echo 'min2 done'

# heat: 0→300K
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/heat
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/heat.mdin -o heat.mdout -p ${PRMTOP} -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/min2/min2.rst7 -r heat.rst7 -x heat.nc -ref ${INPCRD}
echo 'heat done'

# equil: 5 ns NTP
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/equil.mdin -o equil.mdout -p ${PRMTOP} -c /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/heat/heat.rst7 -r equil.rst7 -x equil.nc
echo 'equil done'
echo 'PIPELINE_EQUIL_COMPLETE'

echo "Job finished: $(date)"

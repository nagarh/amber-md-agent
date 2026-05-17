#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=01:00:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/equil2.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/equil2.err
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo
mkdir -p simulations/equil2

pmemd.cuda -O -i mdin/equil2.mdin -o simulations/equil2/equil2.mdout \
  -p system/system.prmtop \
  -c simulations/equil/equil.rst7 -ref simulations/equil/equil.rst7 \
  -r simulations/equil2/equil2.rst7 -x simulations/equil2/equil2.nc
echo "=== DONE ==="

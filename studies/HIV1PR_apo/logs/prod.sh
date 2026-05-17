#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/prod.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/prod.err
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo

pmemd.cuda -O -i mdin/prod.mdin -o simulations/prod/prod.mdout \
  -p system/system.prmtop \
  -c simulations/equil2/equil2.rst7 \
  -r simulations/prod/prod.rst7 -x simulations/prod/prod.nc
echo "=== DONE ==="

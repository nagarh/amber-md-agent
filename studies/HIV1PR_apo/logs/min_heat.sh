#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=01:00:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/min_heat.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/min_heat.err
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo

PRM=system/system.prmtop
INI=system/system.inpcrd

echo "=== MIN1 ==="
pmemd.cuda -O -i mdin/min1.mdin -o simulations/min1/min1.mdout \
  -p $PRM -c $INI -ref $INI \
  -r simulations/min1/min1.rst7

echo "=== MIN2 ==="
pmemd.cuda -O -i mdin/min2.mdin -o simulations/min2/min2.mdout \
  -p $PRM -c simulations/min1/min1.rst7 \
  -r simulations/min2/min2.rst7

echo "=== HEAT ==="
pmemd.cuda -O -i mdin/heat.mdin -o simulations/heat/heat.mdout \
  -p $PRM -c simulations/min2/min2.rst7 -ref simulations/min2/min2.rst7 \
  -r simulations/heat/heat.rst7 -x simulations/heat/heat.nc

echo "=== DONE ==="
ls -lh simulations/*/*.rst7

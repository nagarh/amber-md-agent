#!/bin/bash
#SBATCH --job-name=CDK4_WT_abema
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib/CDK4_WT_abema_%j.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib/CDK4_WT_abema_%j.err
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=168:00:00
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

SYS=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/system/WT_abemaciclib
MDIN=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/mdin
SIMDIR=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib

echo "=== Min1: restrained minimization ==="
pmemd.cuda -O \
  -i  $MDIN/min1.mdin \
  -o  $SIMDIR/min1/min1.mdout \
  -p  $SYS/system.prmtop \
  -c  $SYS/system.inpcrd \
  -r  $SIMDIR/min1/min1.rst7 \
  -ref $SYS/system.inpcrd || { echo "FATAL: min1 failed"; exit 1; }

echo "=== Min2: unrestrained minimization ==="
pmemd.cuda -O \
  -i  $MDIN/min2.mdin \
  -o  $SIMDIR/min2/min2.mdout \
  -p  $SYS/system.prmtop \
  -c  $SIMDIR/min1/min1.rst7 \
  -r  $SIMDIR/min2/min2.rst7 || { echo "FATAL: min2 failed"; exit 1; }

echo "=== Heat: NVT 0→300 K ==="
pmemd.cuda -O \
  -i  $MDIN/heat.mdin \
  -o  $SIMDIR/heat/heat.mdout \
  -p  $SYS/system.prmtop \
  -c  $SIMDIR/min2/min2.rst7 \
  -r  $SIMDIR/heat/heat.rst7 \
  -x  $SIMDIR/heat/heat.nc \
  -ref $SIMDIR/min2/min2.rst7 || { echo "FATAL: heat failed"; exit 1; }

echo "=== Equil: NPT 300 K ==="
pmemd.cuda -O \
  -i  $MDIN/equil.mdin \
  -o  $SIMDIR/equil/equil.mdout \
  -p  $SYS/system.prmtop \
  -c  $SIMDIR/heat/heat.rst7 \
  -r  $SIMDIR/equil/equil.rst7 \
  -x  $SIMDIR/equil/equil.nc \
  -ref $SIMDIR/heat/heat.rst7 || { echo "FATAL: equil failed"; exit 1; }

echo "=== Production: NPT 2.5 ns ==="
pmemd.cuda -O \
  -i  $MDIN/prod.mdin \
  -o  $SIMDIR/prod/prod.mdout \
  -p  $SYS/system.prmtop \
  -c  $SIMDIR/equil/equil.rst7 \
  -r  $SIMDIR/prod/prod.rst7 \
  -x  $SIMDIR/prod/prod.nc || { echo "FATAL: prod failed"; exit 1; }

echo "=== Pipeline complete: WT+abemaciclib ==="

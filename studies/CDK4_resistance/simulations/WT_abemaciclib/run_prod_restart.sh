#!/bin/bash
#SBATCH --job-name=CDK4_WT_abema_prod
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib/CDK4_WT_abema_prod_%j.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib/CDK4_WT_abema_prod_%j.err
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

mkdir -p $SIMDIR/equil2

echo "=== Equil2: 1 ns unrestrained NPT (density convergence) ==="
pmemd.cuda -O \
  -i  $MDIN/equil2.mdin \
  -o  $SIMDIR/equil2/equil2.mdout \
  -p  $SYS/system.prmtop \
  -c  $SIMDIR/equil/equil.rst7 \
  -r  $SIMDIR/equil2/equil2.rst7 \
  -x  $SIMDIR/equil2/equil2.nc || { echo "FATAL: equil2 failed"; exit 1; }

echo "=== Production: NPT 2.5 ns ==="
pmemd.cuda -O \
  -i  $MDIN/prod.mdin \
  -o  $SIMDIR/prod/prod.mdout \
  -p  $SYS/system.prmtop \
  -c  $SIMDIR/equil2/equil2.rst7 \
  -r  $SIMDIR/prod/prod.rst7 \
  -x  $SIMDIR/prod/prod.nc || { echo "FATAL: prod failed"; exit 1; }

echo "=== Pipeline complete: WT+abemaciclib ==="

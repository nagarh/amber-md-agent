#!/bin/bash
#SBATCH --job-name=CDK4_WT_abema_prod
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib/CDK4_WT_abema_final_%j.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib/CDK4_WT_abema_final_%j.err
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

mkdir -p $SIMDIR/prod

echo "=== Production: NPT 2.5 ns with pmemd.cuda (starting from equil2.rst7, density ~1.0 g/cc) ==="
pmemd.cuda -O \
  -i  $MDIN/prod.mdin \
  -o  $SIMDIR/prod/prod.mdout \
  -p  $SYS/system.prmtop \
  -c  $SIMDIR/equil2/equil2.rst7 \
  -r  $SIMDIR/prod/prod.rst7 \
  -x  $SIMDIR/prod/prod.nc || { echo "FATAL: prod failed"; exit 1; }

echo "=== Pipeline complete: WT+abemaciclib ==="

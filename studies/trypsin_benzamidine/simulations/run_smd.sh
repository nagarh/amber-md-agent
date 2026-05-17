#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/simulations
#SBATCH --job-name=tb_smd
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --time=06:00:00
#SBATCH --output=run_smd_%j.out
#SBATCH --error=run_smd_%j.err

set -e
module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

ROOT=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine
PRM=$ROOT/system/system.prmtop
START=$ROOT/simulations/prepull/prepull.rst7
MDIN=$ROOT/mdin/smd.mdin

mkdir -p $ROOT/simulations/smd
cd $ROOT/simulations/smd
# Copy RST so Amber sees short path (80-char limit on DISANG line)
cp $ROOT/mdin/pull.RST pull.RST

echo "=== SMD pull (BEN COM <-> Asp189 CA, 3->17 A, 28 ns) ==="
date
pmemd.cuda -O -i $MDIN -o smd.mdout -p $PRM -c $START \
  -r smd.rst7 -x smd.nc
echo "smd exit $?"
echo "=== DONE: $(date) ==="
ls -lh smd.rst7 smd.nc dist_vs_t.dat
echo "Final dumpave tail:"
tail -3 dist_vs_t.dat

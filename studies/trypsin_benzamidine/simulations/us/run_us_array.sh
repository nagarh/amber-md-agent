#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/simulations/us
#SBATCH --job-name=tb_us
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --time=04:00:00
#SBATCH --output=us_%A_%a.out
#SBATCH --error=us_%A_%a.err
#SBATCH --array=0-28

set -e
module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

ROOT=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine
PRM=$ROOT/system/system.prmtop

# Window centers: 3.0, 3.5, ..., 17.0 (29 windows)
WINDOWS=(3.00 3.50 4.00 4.50 5.00 5.50 6.00 6.50 7.00 7.50 \
         8.00 8.50 9.00 9.50 10.00 10.50 11.00 11.50 12.00 12.50 \
         13.00 13.50 14.00 14.50 15.00 15.50 16.00 16.50 17.00)

W=${WINDOWS[$SLURM_ARRAY_TASK_ID]}
WNAME="w${W/./_}"
WDIR=$ROOT/simulations/us/$WNAME
cd $WDIR

echo "=== US window $WNAME (center r=$W A) — task $SLURM_ARRAY_TASK_ID ==="
date

# Copy mdin templates locally
cp $ROOT/mdin/us_equil.mdin .
cp $ROOT/mdin/us_window.mdin .

echo "--- Equil 1 ns (restraint on) ---"
pmemd.cuda -O -i us_equil.mdin -o equil.mdout -p $PRM -c start.rst7 \
  -r equil.rst7 -x equil.nc
echo "equil exit $?"

echo "--- Production 10 ns ---"
pmemd.cuda -O -i us_window.mdin -o prod.mdout -p $PRM -c equil.rst7 \
  -r prod.rst7 -x prod.nc
echo "prod exit $?"

echo "=== Window $WNAME DONE: $(date) ==="
echo "Samples in prod_dist.dat: $(wc -l < prod_dist.dat)"
tail -3 prod_dist.dat

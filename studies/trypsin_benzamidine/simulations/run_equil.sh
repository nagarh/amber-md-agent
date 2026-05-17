#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/simulations
#SBATCH --job-name=tb_equil
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --time=04:00:00
#SBATCH --output=run_equil_%j.out
#SBATCH --error=run_equil_%j.err

set -e
module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

ROOT=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine
SYS=$ROOT/system
MDIN=$ROOT/mdin
PRM=$SYS/system.prmtop
IC=$SYS/system.inpcrd

mkdir -p $ROOT/simulations/{min,heat,equil_burst,equil2,prepull}
cd $ROOT/simulations

echo "=== MIN1 (restrained 10) ==="
pmemd.cuda -O -i $MDIN/min1.mdin -o min/min1.mdout -p $PRM -c $IC \
  -r min/min1.rst7 -ref $IC
echo "min1 exit $?"

echo "=== MIN2 (unrestrained) ==="
pmemd.cuda -O -i $MDIN/min2.mdin -o min/min2.mdout -p $PRM -c min/min1.rst7 \
  -r min/min2.rst7
echo "min2 exit $?"

echo "=== HEAT NVT 0->300K (restrained 5) ==="
pmemd.cuda -O -i $MDIN/heat.mdin -o heat/heat.mdout -p $PRM -c min/min2.rst7 \
  -r heat/heat.rst7 -x heat/heat.nc -ref min/min2.rst7
echo "heat exit $?"

echo "=== BURST NPT (Berendsen taup=0.5) — 5 iter ==="
prev=heat/heat.rst7
for i in 1 2 3 4 5; do
  pmemd.cuda -O -i $MDIN/equil_burst.mdin -o equil_burst/burst${i}.mdout -p $PRM \
    -c $prev -r equil_burst/burst${i}.rst7 -x equil_burst/burst${i}.nc
  rho=$(grep "Density" equil_burst/burst${i}.mdout | tail -1 | awk '{print $9}')
  echo "Burst iter $i density=$rho"
  prev=equil_burst/burst${i}.rst7
done

echo "=== EQUIL2 NPT 500 ps (restrained 0.5) ==="
pmemd.cuda -O -i $MDIN/equil2.mdin -o equil2/equil2.mdout -p $PRM -c $prev \
  -r equil2/equil2.rst7 -x equil2/equil2.nc -ref $prev
echo "equil2 exit $?"

echo "=== PREPULL NPT MC 1 ns (unrestrained) ==="
pmemd.cuda -O -i $MDIN/prepull.mdin -o prepull/prepull.mdout -p $PRM \
  -c equil2/equil2.rst7 -r prepull/prepull.rst7 -x prepull/prepull.nc
echo "prepull exit $?"

echo "=== DONE: $(date) ==="
ls -lh prepull/prepull.rst7

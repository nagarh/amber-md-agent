#!/bin/bash
#SBATCH --job-name=CDK4_WT_abema_prod
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib/CDK4_WT_abema_prod3_%j.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/CDK4_resistance/simulations/WT_abemaciclib/CDK4_WT_abema_prod3_%j.err
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

echo "=== Equil2: iterative pmemd.cuda restarts until density >= 0.98 g/cc ==="

RST_IN=$SIMDIR/equil/equil.rst7
MAX_ITER=50
iter=0
density=0

while [ $iter -lt $MAX_ITER ]; do
    OUT=$SIMDIR/equil2/equil2_r${iter}.mdout
    RST_OUT=$SIMDIR/equil2/equil2_r${iter}.rst7

    pmemd.cuda -O \
      -i  $MDIN/equil2_short.mdin \
      -o  $OUT \
      -p  $SYS/system.prmtop \
      -c  $RST_IN \
      -r  $RST_OUT \
      -x  /dev/null

    exit_code=$?

    # Extract last density from mdout
    density=$(grep "Density" $OUT 2>/dev/null | tail -1 | awk '{print $NF}')
    echo "  Iteration $iter: exit=$exit_code  density=$density"

    if [ -f "$RST_OUT" ]; then
        # rst7 was written (ntwr=500 ensures this even on crash)
        RST_IN=$RST_OUT
        if [ $exit_code -eq 0 ]; then
            done=$(python3 -c "print('yes' if float('${density:-0}') >= 0.98 else 'no')" 2>/dev/null)
            if [ "$done" = "yes" ]; then
                echo "  Density converged at $density g/cc after $iter iterations"
                cp $RST_OUT $SIMDIR/equil2/equil2.rst7
                break
            fi
        else
            echo "  pmemd.cuda crashed at iter $iter, advancing from checkpoint (density=$density)..."
        fi
    else
        echo "  WARNING: no rst7 at iter $iter, repeating from same input..."
    fi

    iter=$((iter + 1))
done

if [ ! -f "$SIMDIR/equil2/equil2.rst7" ]; then
    echo "FATAL: density did not converge after $MAX_ITER iterations"
    exit 1
fi

echo "=== Production: NPT 2.5 ns with pmemd.cuda ==="
mkdir -p $SIMDIR/prod
pmemd.cuda -O \
  -i  $MDIN/prod.mdin \
  -o  $SIMDIR/prod/prod.mdout \
  -p  $SYS/system.prmtop \
  -c  $SIMDIR/equil2/equil2.rst7 \
  -r  $SIMDIR/prod/prod.rst7 \
  -x  $SIMDIR/prod/prod.nc || { echo "FATAL: prod failed"; exit 1; }

echo "=== Pipeline complete: WT+abemaciclib ==="

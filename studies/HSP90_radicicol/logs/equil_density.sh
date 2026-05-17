#!/bin/bash
#SBATCH --job-name=HSP90_density
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=168:00:00
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/HSP90_density_%j.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/HSP90_density_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

mkdir -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil

echo "=== Density convergence: pmemd.cuda restart loop (target >= 0.98 g/cc) ==="

RST_IN=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/heat/heat.rst7
MAX_ITER=30
TARGET=0.98
iter=0

while [ $iter -lt $MAX_ITER ]; do
    OUT=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/density_r${iter}.mdout
    RST_OUT=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/density_r${iter}.rst7

    pmemd.cuda -O \
      -i  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil_density_burst.mdin \
      -o  $OUT \
      -p  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/system/system.prmtop \
      -c  $RST_IN \
      -r  $RST_OUT \
      -x  /dev/null

    exit_code=$?
    density=$(grep 'Density' $OUT 2>/dev/null | grep -v '0\.00' | tail -1 | awk '{print $NF}')
    echo "  Iteration $iter: exit=$exit_code  density=$density"

    if [ -f "$RST_OUT" ]; then
        RST_IN=$RST_OUT
        if [ $exit_code -eq 0 ]; then
            converged=$(python3 -c "print('yes' if float('${density:-0}') >= $TARGET else 'no')" 2>/dev/null)
            if [ "$converged" = "yes" ]; then
                echo "  Density converged at $density g/cc after $iter iterations"
                cp $RST_OUT /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/equil.rst7
                break
            fi
        else
            echo "  Crashed at iter $iter, advancing from checkpoint (density=$density)..."
        fi
    else
        echo "  WARNING: no rst7 at iter $iter, repeating..."
    fi

    iter=$((iter + 1))
done

if [ ! -f "/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/equil.rst7" ]; then
    echo "FATAL: density did not converge after $MAX_ITER iterations"
    exit 1
fi

mkdir -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/prod
echo "=== Production ==="
pmemd.cuda -O \
  -i  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/mdin/prod.mdin \
  -o  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/prod/prod.mdout \
  -p  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/system/system.prmtop \
  -c  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/equil/equil.rst7 \
  -r  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/prod/prod.rst7 \
  -x  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSP90_radicicol/simulations/prod/prod.nc || { echo "FATAL: prod failed"; exit 1; }

echo "=== Pipeline complete ==="

#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/CDK2_apo
#SBATCH --job-name=CDK2_apo_pipeline
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=defq
#SBATCH --time=08:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=logs/CDK2_apo_pipeline_%j.out
#SBATCH --error=logs/CDK2_apo_pipeline_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
nvidia-smi | head -10 || true

WORK=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/CDK2_apo
PRMTOP=$WORK/system/system.prmtop
INPCRD=$WORK/system/system.inpcrd
MIN1=$WORK/simulations/min1
MIN2=$WORK/simulations/min2
HEAT=$WORK/simulations/heat
EQUIL=$WORK/simulations/equil
EQUIL2=$WORK/simulations/equil2
PROD=$WORK/simulations/prod

set -e

# --- MIN1 ---
echo "=== MIN1: restrained backbone minimization ==="
pmemd.cuda -O \
  -i $MIN1/min1.mdin -o $MIN1/min1.mdout \
  -p $PRMTOP -c $INPCRD -r $MIN1/min1.rst7 -ref $INPCRD
echo "MIN1 done"

# --- MIN2 ---
echo "=== MIN2: full minimization ==="
pmemd.cuda -O \
  -i $MIN2/min2.mdin -o $MIN2/min2.mdout \
  -p $PRMTOP -c $MIN1/min1.rst7 -r $MIN2/min2.rst7
echo "MIN2 done"

# --- HEAT ---
echo "=== HEAT: NVT 0->300 K (100 ps) ==="
pmemd.cuda -O \
  -i $HEAT/heat.mdin -o $HEAT/heat.mdout \
  -p $PRMTOP -c $MIN2/min2.rst7 -r $HEAT/heat.rst7 -ref $MIN2/min2.rst7
echo "HEAT done"

# --- EQUIL BURST (density convergence) ---
echo "=== EQUIL BURST: NPT density convergence ==="
BURST_RST=$HEAT/heat.rst7
CONVERGED=0
for i in $(seq 1 10); do
  MDOUT=$EQUIL/equil_${i}.mdout
  RST_OUT=$EQUIL/equil_${i}.rst7
  pmemd.cuda -O \
    -i $EQUIL/equil.mdin -o $MDOUT \
    -p $PRMTOP -c $BURST_RST -r $RST_OUT
  BURST_RST=$RST_OUT
  DENSITY=$(grep 'DENSITY' $MDOUT | tail -5 | awk '{s+=$5; n++} END {if(n>0) printf "%.4f", s/n; else print 0}')
  echo "Burst iter ${i}: mean density=${DENSITY} g/cc"
  OK=$(python3 -c "d=float('${DENSITY}' or '0'); print('yes' if 0.95<=d<=1.05 else 'no')")
  if [ "$OK" = "yes" ]; then
    echo "Density converged at iter ${i}"
    CONVERGED=1
    break
  fi
done
if [ "$CONVERGED" -eq 0 ]; then
  echo "WARNING: density not converged after 10 iterations, proceeding anyway"
fi

# --- EQUIL2 ---
echo "=== EQUIL2: NPT restrained 500 ps ==="
pmemd.cuda -O \
  -i $EQUIL2/equil2.mdin -o $EQUIL2/equil2.mdout \
  -p $PRMTOP -c $BURST_RST -r $EQUIL2/equil2.rst7 -ref $BURST_RST
echo "EQUIL2 done"

# --- PRODUCTION ---
echo "=== PRODUCTION: NPT MC barostat 20 ns ==="
pmemd.cuda -O \
  -i $PROD/prod.mdin -o $PROD/prod.mdout \
  -p $PRMTOP -c $EQUIL2/equil2.rst7 -r $PROD/prod.rst7 -x $PROD/prod.nc
echo "PRODUCTION done"

echo "=== ALL STEPS COMPLETE ==="
echo "Job finished: $(date)"

#!/bin/bash
#SBATCH --job-name=equil_density_HSA
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=168:00:00
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil//equil_density_HSA_%j.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil//equil_density_HSA_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

mkdir -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil

echo "=== Density convergence: pmemd.cuda restart loop "
echo "    target 1.000 +/- 0.050 g/cc, fluctuation < 0.020"

RST_IN=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/equil2.rst7
MAX_ITER=30
TARGET=1.0
TOL=0.05
FLUCT_MAX=0.02
iter=0

# Python helper: parse time-series Density lines only (skip AVERAGES / RMS FLUCT sections).
parse_density() {
    python3 - "$1" "$TARGET" "$TOL" "$FLUCT_MAX" <<'PYEOF'
import sys, re
path, target, tol, fmax = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
try: text = open(path).read()
except Exception: print('ERR no_mdout 0 0'); sys.exit(0)
# Find time-series block end (start of AVERAGES section)
avg_idx = text.find('A V E R A G E S')
ts = text[:avg_idx] if avg_idx > 0 else text
vals = [float(m) for m in re.findall(r'Density\s+=\s+([0-9.]+)', ts) if float(m) > 0.1]
if not vals: print('ERR no_density 0 0'); sys.exit(0)
tail = vals[-5:] if len(vals) >= 5 else vals
mean = sum(tail)/len(tail); fluct = max(tail) - min(tail)
ok = (abs(mean - target) <= tol) and (fluct < fmax)
print(f"{'YES' if ok else 'NO'} {mean:.4f} {fluct:.4f}")
PYEOF
}

while [ $iter -lt $MAX_ITER ]; do
    OUT=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/density_r${iter}.mdout
    RST_OUT=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/density_r${iter}.rst7

    pmemd.cuda -O \
      -i  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/equil_density_burst.mdin \
      -o  $OUT \
      -p  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system/system.prmtop \
      -c  $RST_IN \
      -r  $RST_OUT \
      -x  /dev/null

    exit_code=$?
    read STATUS MEAN FLUCT <<< $(parse_density $OUT)
    echo "  Iteration $iter: exit=$exit_code  mean_density=$MEAN  fluct=$FLUCT  converged=$STATUS"

    if [ -f "$RST_OUT" ]; then
        RST_IN=$RST_OUT
        if [ $exit_code -eq 0 ] && [ "$STATUS" = "YES" ]; then
            echo "  Density converged: mean=$MEAN g/cc, fluct=$FLUCT after $iter iterations"
            cp $RST_OUT /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/equil2.rst7
            break
        elif [ $exit_code -ne 0 ]; then
            echo "  Crashed at iter $iter, advancing from checkpoint (mean=$MEAN)..."
        fi
    else
        echo "  WARNING: no rst7 at iter $iter, repeating..."
    fi

    iter=$((iter + 1))
done

if [ ! -f "/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/equil2.rst7" ]; then
    echo "FATAL: density did not converge after $MAX_ITER iterations"
    exit 1
fi

mkdir -p /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod
echo "=== Production ==="
pmemd.cuda -O \
  -i  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod/prod.mdin \
  -o  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod/prod.mdout \
  -p  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/system/system.prmtop \
  -c  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/equil/equil2.rst7 \
  -r  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod/prod.rst7 \
  -x  /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HSA_ibuprofen/simulations/prod/prod.nc || { echo "FATAL: prod failed"; exit 1; }

echo "=== Pipeline complete ==="

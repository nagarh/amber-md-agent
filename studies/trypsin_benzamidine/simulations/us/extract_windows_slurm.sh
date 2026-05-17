#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/simulations/us
#SBATCH --job-name=tb_extract
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:20:00
#SBATCH --output=extract_%j.out
#SBATCH --error=extract_%j.err

set -e
module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

ROOT=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine
cd $ROOT/simulations/us

echo "=== cpptraj extract windows from SMD ==="
cpptraj -i extract_windows.in > extract.log 2>&1
echo "cpptraj exit $?"

echo "=== Verify rst7 files created ==="
for d in w*; do
  if [ -f "$d/start.rst7" ]; then
    sz=$(stat -c%s "$d/start.rst7")
    echo "  $d/start.rst7 OK ($sz bytes)"
  else
    echo "  $d/start.rst7 MISSING"
  fi
done
echo "DONE"

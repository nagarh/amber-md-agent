#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/1UBQ
#SBATCH --job-name=md_1UBQ
#SBATCH --partition=defq
#SBATCH --get-user-env
#SBATCH --nodes=1
#SBATCH --tasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=168:00:00
#SBATCH --output=md_1UBQ_%j.out
#SBATCH --error=md_1UBQ_%j.err

module load amber/24
set -e

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

cd system && tleap -f tleap.in > ../logs/tleap.log 2>&1 && cd ..
pmemd.cuda -O -i simulations/min1/min1.mdin -o simulations/min1/min1.mdout -p system/system.prmtop -c system/system.inpcrd -r simulations/min1/min1.rst7 -ref system/system.inpcrd
pmemd.cuda -O -i simulations/min2/min2.mdin -o simulations/min2/min2.mdout -p system/system.prmtop -c simulations/min1/min1.rst7 -r simulations/min2/min2.rst7
pmemd.cuda -O -i simulations/heat/heat.mdin -o simulations/heat/heat.mdout -p system/system.prmtop -c simulations/min2/min2.rst7 -r simulations/heat/heat.rst7 -x simulations/heat/heat.nc -ref simulations/min2/min2.rst7
pmemd.cuda -O -i simulations/equil/equil.mdin -o simulations/equil/equil.mdout -p system/system.prmtop -c simulations/heat/heat.rst7 -r simulations/equil/equil.rst7 -x simulations/equil/equil.nc -ref simulations/min2/min2.rst7
pmemd.cuda -O -i simulations/prod/prod.mdin -o simulations/prod/prod.mdout -p system/system.prmtop -c simulations/equil/equil.rst7 -r simulations/prod/prod.rst7 -x simulations/prod/prod.nc

echo "Job finished: $(date)"

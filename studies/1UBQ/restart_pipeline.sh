#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/1UBQ
#SBATCH --job-name=md_1UBQ_restart
#SBATCH --partition=defq
#SBATCH --get-user-env
#SBATCH --nodes=1
#SBATCH --tasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=168:00:00
#SBATCH --output=md_1UBQ_restart_%j.out
#SBATCH --error=md_1UBQ_restart_%j.err

module load amber/24
set -e

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

pmemd.cuda -O -i simulations/equil2/equil2.mdin -o simulations/equil2/equil2.mdout -p system/system.prmtop -c simulations/equil/equil.rst7 -r simulations/equil2/equil2.rst7 -x simulations/equil2/equil2.nc
pmemd.cuda -O -i simulations/prod/prod.mdin -o simulations/prod/prod.mdout -p system/system.prmtop -c simulations/equil2/equil2.rst7 -r simulations/prod/prod.rst7 -x simulations/prod/prod.nc

echo "Job finished: $(date)"

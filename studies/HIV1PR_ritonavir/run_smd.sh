#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/smd
#SBATCH --job-name=HIV1PR_smd
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=24:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=HIV1PR_smd_%j.out
#SBATCH --error=HIV1PR_smd_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Working dir: $(pwd)"

echo "Running SMD pull: ritonavir out of HIV-1 PR active site"
pmemd.cuda -O \
  -i /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/smd/smd.mdin \
  -o /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/smd/smd.mdout \
  -p /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system/system.prmtop \
  -c /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/equil/equil.rst7 \
  -r /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/smd/smd.rst7 \
  -x /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/smd/smd.nc \
  -ref /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/equil/equil.rst7

echo "SMD complete"
echo "Job finished: $(date)"

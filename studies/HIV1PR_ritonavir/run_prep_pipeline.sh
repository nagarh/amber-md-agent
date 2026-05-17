#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir
#SBATCH --job-name=HIV1PR_prep
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=48:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=HIV1PR_prep_%j.out
#SBATCH --error=HIV1PR_prep_%j.err

module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "Directory: $(pwd)"
nvidia-smi || true

echo 'Step 1: min1 - restrained minimization'
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min1/min1.mdin -o /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min1/min1.mdout -p /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system/system.inpcrd -r /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min1/min1.rst7 -ref /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system/system.inpcrd
echo 'Step 2: min2 - unrestrained minimization'
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min2/min2.mdin -o /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min2/min2.mdout -p /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min1/min1.rst7 -r /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min2/min2.rst7
echo 'Step 3: heat - 0 to 300 K'
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/heat/heat.mdin -o /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/heat/heat.mdout -p /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min2/min2.rst7 -r /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/heat/heat.rst7 -x /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/heat/heat.nc -ref /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/min2/min2.rst7
echo 'Step 4: equil - NPT 2 ns'
pmemd.cuda -O -i /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/equil/equil.mdin -o /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/equil/equil.mdout -p /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/heat/heat.rst7 -r /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/equil/equil.rst7 -x /home/hn533621/Portfolio/amber-md-agent/studies/HIV1PR_ritonavir/simulations/equil/equil.nc
echo 'Pipeline complete'

echo "Job finished: $(date)"

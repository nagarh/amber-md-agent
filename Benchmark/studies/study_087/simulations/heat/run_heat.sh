#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/heat
#SBATCH --job-name=heat_087
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=04:00:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/heat_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/heat_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/heat
pmemd.cuda -O -i /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/heat/heat.mdin -p /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system/ompf_membrane.prmtop -c /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/min2/min2.rst7 -ref /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/simulations/min2/min2.rst7 \
   -o heat.mdout -r heat.rst7 -x heat.nc -inf heat.mdinfo
echo "exit: $?"

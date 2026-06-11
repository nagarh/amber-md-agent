#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system
#SBATCH --job-name=autoimg_087
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:20:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/autoimg_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/autoimg_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system
cpptraj -i autoimage.in > autoimage.out 2>&1
echo "exit: $?"
ls -la ompf_membrane_centered.inpcrd 2>/dev/null

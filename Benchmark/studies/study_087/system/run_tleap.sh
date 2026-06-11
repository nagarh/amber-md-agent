#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system
#SBATCH --job-name=tleap_087
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:30:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/tleap_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/tleap_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system
tleap -f build.in > tleap.out 2>&1
echo "tleap exit: $?"
echo "Job finished: $(date)"
ls -la ompf_membrane.prmtop ompf_membrane.inpcrd 2>/dev/null

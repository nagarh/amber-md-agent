#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:15:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/tleap.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/tleap.err
module load amber/24
source /opt/shared/apps/amber/24/amber.sh
cd /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/system/
tleap -f tleap.in > leap.log 2>&1
tail -40 leap.log
ls -lh system.prmtop system.inpcrd

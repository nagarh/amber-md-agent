#!/bin/bash
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --time=00:15:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/analysis.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/logs/analysis.err
module load amber/24
source /opt/shared/apps/amber/24/amber.sh
cpptraj -i /home/hn533621/Portfolio/amber-md-agent-improvements/studies/HIV1PR_apo/analysis/analysis.in

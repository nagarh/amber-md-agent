#!/bin/bash
#SBATCH -D /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system
#SBATCH --job-name=memgen_087
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=24:00:00
#SBATCH --output=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/memgen_%j.out
#SBATCH --error=/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/logs/memgen_%j.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

echo "Job started: $(date)"
echo "Node: $(hostname)"
cd /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system

# Remove stale packed output so packmol-memgen actually repacks (it skips if bilayer.pdb exists)
rm -f bilayer.pdb PROT0.pdb packmol.inp packmol_*.pdb ompf_membrane_leap.pdb

# OmpF trimer embedded in POPE:POPG 3:1 E. coli OM mimic.
# Feed STANDARD-named trimer (HIS/ASP/GLU) — packmol-memgen's preprocessing silently
# DROPS non-standard names (HID/ASH/GLH). Protonation renames applied to bilayer.pdb AFTER.
# --ppm  : orient barrel along membrane normal (z) via OPM/PPM3
# --notprotonate --nottrim : do NOT let packmol re-protonate (preserve our propka decisions);
#                            tLEaP adds H per residue name afterwards
# --dist / --dist_wat 17.5 : water layer each side
# --salt K+ 0.35 M : KCl; 0.35 needed to neutralize anionic POPG + protein, plus bulk salt
packmol-memgen \
    --pdb trimer.pdb \
    --lipids POPE:POPG --ratio 3:1 \
    --ppm \
    --notprotonate --nottrim \
    --salt --salt_c K+ --saltcon 0.40 \
    --dist 17.5 --dist_wat 17.5 \
    --output bilayer.pdb \
    --nloop 50 --nloop_all 50

echo "Exit code: $?"
echo "Job finished: $(date)"
ls -la /data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system/*.pdb

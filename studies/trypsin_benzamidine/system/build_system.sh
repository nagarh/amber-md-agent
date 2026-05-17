#!/bin/bash
#SBATCH -D /home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/system
#SBATCH --job-name=tb_build
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=01:30:00
#SBATCH --output=build_system_%j.out
#SBATCH --error=build_system_%j.err

set -e
module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

WORKDIR=/home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine/system
cd "$WORKDIR"

echo "== Step 0: pdb4amber on protein (--noter to keep chymotrypsinogen-numbered chain continuous, keep CONECT for SS) =="
pdb4amber -i protein_for_pdb4amber.pdb -o protein_clean_amber.pdb --noter 2>&1 | tail -20
echo "CONECT records: $(grep -c ^CONECT protein_clean_amber.pdb)"
echo "TER records: $(grep -c ^TER protein_clean_amber.pdb)"

echo "== Step 1: antechamber on BEN (cationic +1) =="
if [ ! -f ligand.mol2 ]; then
  antechamber -i ligand_ready.sdf -fi sdf -o ligand.mol2 -fo mol2 \
      -c bcc -at gaff2 -nc 1 -rn BEN -pf y
fi

echo "== Step 2: parmchk2 =="
if [ ! -f ligand.frcmod ]; then
  parmchk2 -i ligand.mol2 -f mol2 -o ligand.frcmod
fi

echo "== Step 3: tleap build =="
cat > tleap.in <<EOF
source leaprc.protein.ff14SB
source leaprc.water.tip3p
source leaprc.gaff2
loadAmberParams frcmod.ionsjc_tip3p
loadAmberParams frcmod.ions234lm_126_tip3p

loadAmberParams ${WORKDIR}/ligand.frcmod
BEN = loadMol2 ${WORKDIR}/ligand.mol2

prot = loadPdb ${WORKDIR}/protein_clean_amber.pdb
calc = loadPdb ${WORKDIR}/calcium.pdb

sys = combine {prot calc BEN}
charge sys

solvateBox sys TIP3PBOX 18.0
addIons sys Na+ 0
addIons sys Cl- 0

saveAmberParm sys ${WORKDIR}/system.prmtop ${WORKDIR}/system.inpcrd
savePdb sys ${WORKDIR}/system_solvated.pdb
charge sys
quit
EOF

tleap -f tleap.in > tleap.log 2>&1
echo "tleap exit: $?"

echo "== Step 4: validate =="
grep -E "Errors = |Could not|Fatal|FATAL|disulphide|bond:" tleap.log || echo "(no error patterns)"
ls -lh system.prmtop system.inpcrd 2>&1 || true
echo "JOB DONE: $(date)"

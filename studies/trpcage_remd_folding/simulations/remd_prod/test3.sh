#!/bin/bash
#SBATCH --job-name=remd_test3
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --time=00:10:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/remd_test3.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/remd_test3.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

TEST=/tmp/remd_test3
mkdir -p ${TEST}
cd ${TEST}

PRMTOP=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop
PREQ=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/pre_equil

cat > ${TEST}/r.mdin << 'EOF'
Plain MD test
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=500,
  dt=0.002,
  temp0=300.0, tempi=300.0,
  ntt=3, gamma_ln=2.0,
  ntb=1, ntp=0,
  ntc=2, ntf=2,
  cut=10.0,
  ntwx=0, ntwr=500, ntpr=100,
  ioutfm=1,
 /

EOF

echo "=== plain pmemd.MPI (2 cores, no REMD) ==="
mpirun -np 2 pmemd.MPI -O -i ${TEST}/r.mdin -p ${PRMTOP} -c ${PREQ}/preq_03.rst7 -o ${TEST}/r.mdout -r ${TEST}/r.rst7 -inf ${TEST}/r.mdinfo
EXIT=$?
echo "Exit: ${EXIT}"
tail -20 ${TEST}/r.mdout 2>/dev/null

#!/bin/bash
#SBATCH --job-name=remd_test2
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --time=00:10:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/remd_test2.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/remd_test2.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

REMD=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/remd_prod
TEST=/tmp/remd_test2
mkdir -p ${TEST}
cd ${TEST}

# copy first 2 mdins, edit numexchg to 2
sed 's/numexchg=100000/numexchg=2/' ${REMD}/remd_00.mdin > ${TEST}/r0.mdin
sed 's/numexchg=100000/numexchg=2/' ${REMD}/remd_01.mdin > ${TEST}/r1.mdin

PRMTOP=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop
PREQ=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/pre_equil

cat > ${TEST}/group.in << EOF
-O -i ${TEST}/r0.mdin -p ${PRMTOP} -c ${PREQ}/preq_00.rst7 -o ${TEST}/r0.mdout -r ${TEST}/r0.rst7 -x ${TEST}/r0.nc -inf ${TEST}/r0.mdinfo
-O -i ${TEST}/r1.mdin -p ${PRMTOP} -c ${PREQ}/preq_01.rst7 -o ${TEST}/r1.mdout -r ${TEST}/r1.rst7 -x ${TEST}/r1.nc -inf ${TEST}/r1.mdinfo
EOF

echo "=== groupfile ===" && cat ${TEST}/group.in
echo "=== r0.mdin tail ===" && tail -3 ${TEST}/r0.mdin | cat -A
echo "=== run ==="

mpirun -np 2 pmemd.MPI -ng 2 -groupfile ${TEST}/group.in -rem 1 -remlog ${TEST}/remd.log
EXIT=$?
echo "Exit: ${EXIT}"

echo "=== remd.log ===" && cat ${TEST}/remd.log 2>/dev/null | head -30
echo "=== r0.mdout tail ===" && tail -30 ${TEST}/r0.mdout 2>/dev/null
echo "=== r1.mdout tail ===" && tail -30 ${TEST}/r1.mdout 2>/dev/null

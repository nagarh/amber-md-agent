#!/bin/bash
#SBATCH --job-name=remd_test
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/remd_test.out
#SBATCH --error=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/logs/remd_test.err

module load gnu12/12.2.0
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

REMD_DIR=/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/remd_prod

# tiny 2-replica test: 2 exchange steps only (nstlim=500 × numexchg=2 = 1000 steps = 2 ps)
# write a quick test groupfile
cat > /tmp/test_group.in << 'EOF'
-O -i /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/remd_prod/remd_00.mdin -p /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/pre_equil/preq_00.rst7 -o /tmp/test_r0.mdout -r /tmp/test_r0.rst7 -x /tmp/test_r0.nc -inf /tmp/test_r0.mdinfo
-O -i /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/remd_prod/remd_01.mdin -p /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop -c /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/pre_equil/preq_01.rst7 -o /tmp/test_r1.mdout -r /tmp/test_r1.rst7 -x /tmp/test_r1.nc -inf /tmp/test_r1.mdinfo
EOF

# Override numexchg to just 2 for test — write temp mdin
sed 's/numexchg=100000/numexchg=2/' /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/remd_prod/remd_00.mdin > /tmp/test_r0.mdin
sed 's/numexchg=100000/numexchg=2/' /home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding/simulations/remd_prod/remd_01.mdin > /tmp/test_r1.mdin

# update groupfile to use test mdins
sed -i 's|remd_00.mdin|/tmp/test_r0.mdin|' /tmp/test_group.in
sed -i 's|remd_01.mdin|/tmp/test_r1.mdin|' /tmp/test_group.in

echo "=== pmemd.MPI path: $(which pmemd.MPI 2>/dev/null || echo NOT_FOUND) ==="
echo "=== test groupfile: ===" && cat /tmp/test_group.in

mpirun -np 2 pmemd.MPI \
  -ng 2 \
  -groupfile /tmp/test_group.in \
  -rem 1 \
  -remlog /tmp/test_remd.log

echo "Exit: $?"
cat /tmp/test_remd.log 2>/dev/null | head -20
cat /tmp/test_r0.mdout 2>/dev/null | grep "NSTEP\|ERROR\|error" | head -10

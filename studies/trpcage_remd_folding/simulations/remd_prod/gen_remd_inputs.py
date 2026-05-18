#!/usr/bin/env python3
"""Generate 16 REMD production mdin files, groupfile, and SLURM script."""
import math, os

T_MIN, T_MAX, N_REP = 270.0, 600.0, 16
temps = [T_MIN * math.exp(i * math.log(T_MAX / T_MIN) / (N_REP - 1)) for i in range(N_REP)]
temps[-1] = T_MAX

STUDY = "/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding"
PRMTOP = "/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_1ns_stress/system/system.prmtop"
PREQ_DIR = f"{STUDY}/simulations/pre_equil"
REMD_DIR = f"{STUDY}/simulations/remd_prod"

MDIN_TEMPLATE = """\
Trp-cage T-REMD replica {idx:02d} at {T:.1f} K
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=500,
  dt=0.002,
  temp0={T:.1f}, tempi={T:.1f},
  ntt=3, gamma_ln=2.0,
  ntb=1, ntp=0,
  ntc=2, ntf=2,
  cut=10.0,
  ntwe=0, ntwx=5000, ntwr=50000, ntpr=500,
  numexchg=100000,
  ioutfm=1,
 /

"""

# mdin files
for i, T in enumerate(temps):
    fname = f"remd_{i:02d}.mdin"
    with open(fname, "w") as f:
        f.write(MDIN_TEMPLATE.format(idx=i, T=T))

# groupfile: one line per replica
with open("remd_group.in", "w") as f:
    for i in range(N_REP):
        line = (
            f"-O -i {REMD_DIR}/remd_{i:02d}.mdin "
            f"-p {PRMTOP} "
            f"-c {PREQ_DIR}/preq_{i:02d}.rst7 "
            f"-o {REMD_DIR}/remd_{i:02d}.mdout "
            f"-r {REMD_DIR}/remd_{i:02d}.rst7 "
            f"-x {REMD_DIR}/remd_{i:02d}.nc "
            f"-inf {REMD_DIR}/remd_{i:02d}.mdinfo\n"
        )
        f.write(line)

print(f"Generated {N_REP} mdin files + remd_group.in")
for i, T in enumerate(temps):
    print(f"  Replica {i:02d}: {T:.1f} K")

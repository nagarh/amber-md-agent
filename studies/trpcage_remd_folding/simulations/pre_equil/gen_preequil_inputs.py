#!/usr/bin/env python3
"""Generate 16 pre-equilibration mdin files for Trp-cage REMD."""
import math, os

# Geometric temperature ladder: 270 -> 600 K, 16 replicas
T_MIN, T_MAX, N_REP = 270.0, 600.0, 16
temps = [T_MIN * math.exp(i * math.log(T_MAX / T_MIN) / (N_REP - 1)) for i in range(N_REP)]
temps[-1] = T_MAX  # enforce exact endpoint

STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MDIN_TEMPLATE = """\
Trp-cage REMD pre-equil replica {idx:02d} at {T:.1f} K
 &cntrl
  imin=0, irest=1, ntx=5,
  nstlim=50000,
  dt=0.002,
  temp0={T:.1f}, tempi={T:.1f},
  ntt=3, gamma_ln=2.0,
  ntb=1, ntp=0,
  ntc=2, ntf=2,
  cut=10.0,
  ntwe=0, ntwx=0, ntwr=50000, ntpr=5000,
  ioutfm=1,
 /

"""

for i, T in enumerate(temps):
    fname = f"preq_{i:02d}.mdin"
    with open(fname, "w") as f:
        f.write(MDIN_TEMPLATE.format(idx=i, T=T))

print("Temperatures:")
for i, T in enumerate(temps):
    print(f"  {i:02d}: {T:.1f} K")
print(f"\nGenerated {N_REP} mdin files.")

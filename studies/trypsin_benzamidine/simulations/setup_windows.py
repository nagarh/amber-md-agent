"""Generate per-window DISANG restraint files + cpptraj script to harvest start configs.
Run after SMD completes."""
import os
import numpy as np

ROOT = "/home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine"
SMD_NC = f"{ROOT}/simulations/smd/smd.nc"
SMD_DIST = f"{ROOT}/simulations/smd/dist_vs_t.dat"
PRM = f"{ROOT}/system/system.prmtop"

WINDOWS = np.arange(3.0, 17.5, 0.5)  # 29: 3.0, 3.5, ..., 17.0
K_REST = 10.0
BEN_HEAVY = list(range(3222, 3231))
ASP_CA = 2467

dist = np.loadtxt(SMD_DIST)
r_actual = dist[:, 1]
print(f"SMD samples: {len(dist)}  r range: {r_actual.min():.2f}-{r_actual.max():.2f}")

# DUMPAVE every 500 steps; trajectory ntwx=10000 steps -> 1 traj frame per 20 dumpave rows
DUMP_PER_FRAME = 20

window_dir = f"{ROOT}/simulations/us"
os.makedirs(window_dir, exist_ok=True)
cpptraj_lines = [f"parm {PRM}", f"trajin {SMD_NC}"]
window_info = []
for w in WINDOWS:
    idx_dump = int(np.argmin(np.abs(r_actual - w)))
    idx_traj = idx_dump // DUMP_PER_FRAME + 1  # cpptraj 1-based
    actual_r = r_actual[idx_dump]
    wname = f"w{w:.2f}".replace(".", "_")
    wd = f"{window_dir}/{wname}"
    os.makedirs(wd, exist_ok=True)
    # DISANG
    igr1 = ",".join(str(i) for i in BEN_HEAVY) + ",0"
    open(f"{wd}/window.RST", "w").write(
        f""" &rst
   iat=-1, -1,
   r1=0.0, r2={w:.2f}, r3={w:.2f}, r4=99.0,
   rk2={K_REST}, rk3={K_REST},
   igr1={igr1},
   igr2={ASP_CA},0,
 /
"""
    )
    # cpptraj line: extract single frame as rst7
    cpptraj_lines.append(f"trajout {wd}/start.rst7 restart onlyframes {idx_traj}")
    window_info.append((w, idx_traj, actual_r))
    print(f"  win r={w:.2f} -> traj frame {idx_traj} actual_r={actual_r:.2f}")

cpptraj_lines.append("run")
cpptraj_lines.append("quit")
open(f"{ROOT}/simulations/us/extract_windows.in", "w").write("\n".join(cpptraj_lines))

# Metafile (Grossfield WHAM: timeseries_path  rc_center  k_force)
# Note: WHAM expects k where V = (1/2)k(r-r0)^2; Amber rk2 in V = rk*(r-r0)^2 -> WHAM k = 2*rk
meta = f"{ROOT}/simulations/us/metafile.dat"
with open(meta, "w") as f:
    for w, _, _ in window_info:
        wname = f"w{w:.2f}".replace(".", "_")
        f.write(f"{window_dir}/{wname}/prod_dist.dat  {w:.2f}  {2*K_REST:.2f}\n")
print(f"Windows: {len(window_info)}  metafile: {meta}")
print(f"cpptraj script: {ROOT}/simulations/us/extract_windows.in")

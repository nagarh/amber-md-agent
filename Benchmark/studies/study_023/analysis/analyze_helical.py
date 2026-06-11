#!/usr/bin/env python
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AN = "/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_023/analysis"

# ---- Parse BPstep.nastruct.dat ----
# cols: Frame BP1 BP2 Shift Slide Rise Tilt Roll Twist Zp Major Minor
rows = []
with open(f"{AN}/BPstep.nastruct.dat") as f:
    for line in f:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        # Frame, BP1(a-b), BP2(a-b), then numbers
        frame = int(p[0]); bp1 = p[1]; bp2 = p[2]
        vals = [np.nan if x == "----" else float(x) for x in p[3:]]
        rows.append((frame, bp1, bp2, *vals))

# Step label by (bp1,bp2); collect per-step arrays
from collections import OrderedDict
steps = OrderedDict()
for r in rows:
    frame, bp1, bp2 = r[0], r[1], r[2]
    shift, slide, rise, tilt, roll, twist, zp, major, minor = r[3:12]
    key = f"{bp1}/{bp2}"
    steps.setdefault(key, {"rise": [], "roll": [], "twist": [], "major": [], "minor": []})
    steps[key]["rise"].append(rise)
    steps[key]["roll"].append(roll)
    steps[key]["twist"].append(twist)
    steps[key]["major"].append(major)
    steps[key]["minor"].append(minor)

step_keys = list(steps.keys())
n_steps = len(step_keys)
print(f"n base-pair steps = {n_steps}, frames/step = {len(steps[step_keys[0]]['rise'])}")

def ms(a):
    a = np.array(a, float)
    a = a[~np.isnan(a)]
    return (np.mean(a), np.std(a)) if a.size else (np.nan, np.nan)

print("\nPer-step averages (mean +/- SD over trajectory):")
print(f"{'Step':<12}{'Rise(A)':>16}{'Roll(deg)':>16}{'Twist(deg)':>16}")
per_step = {}
for k in step_keys:
    rm, rs = ms(steps[k]["rise"]); rom, ros = ms(steps[k]["roll"]); tm, ts = ms(steps[k]["twist"])
    per_step[k] = (rm, rs, rom, ros, tm, ts)
    print(f"{k:<12}{rm:>8.2f}+/-{rs:<5.2f}{rom:>8.2f}+/-{ros:<5.2f}{tm:>8.2f}+/-{ts:<5.2f}")

# ---- Overall duplex averages ----
def pool(param, exclude_terminal=False):
    out = []
    keys = step_keys[1:-1] if exclude_terminal else step_keys
    for k in keys:
        out.extend([v for v in steps[k][param] if not np.isnan(v)])
    return np.array(out, float)

print("\n================ OVERALL DUPLEX AVERAGES ================")
for label, excl in [("ALL 11 steps", False), ("interior 9 steps (terminal excluded)", True)]:
    rise = pool("rise", excl); roll = pool("roll", excl); twist = pool("twist", excl)
    print(f"\n[{label}]")
    print(f"  Rise  = {rise.mean():.2f} +/- {rise.std():.2f} A")
    print(f"  Roll  = {roll.mean():.2f} +/- {roll.std():.2f} deg")
    print(f"  Twist = {twist.mean():.2f} +/- {twist.std():.2f} deg")

# groove widths (El Hassan/Calladine, 3dna) interior only
maj = pool("major", True); mino = pool("minor", True)
print(f"\n  Major groove (El Hassan) = {maj.mean():.2f} +/- {maj.std():.2f} A")
print(f"  Minor groove (El Hassan) = {mino.mean():.2f} +/- {mino.std():.2f} A")

# ---- RMSD convergence (second half) ----
rmsd = np.loadtxt(f"{AN}/rmsd_core.dat")
t = rmsd[:,0]*0.01  # ns (10 ps/frame)
half = len(rmsd)//2
print("\n================ RMSD (core, terminal bp excluded) ================")
print(f"  whole: mean={rmsd[:,1].mean():.2f} A  2nd-half: mean={rmsd[half:,1].mean():.2f} +/- {rmsd[half:,1].std():.2f} A")
d1 = rmsd[:half,1].mean(); d2 = rmsd[half:,1].mean()
print(f"  drift (2nd-half mean - 1st-half mean) = {d2-d1:+.3f} A")

# ---- Plots ----
# 1) per-step bar plots with crystal reference lines
xs = np.arange(n_steps)
labels = step_keys
fig, axes = plt.subplots(3,1, figsize=(10,11), sharex=True)
for ax, param, cryst, ylab, refname in [
    (axes[0], "rise", 3.34, "Rise (A)", "B-DNA ~3.3-3.4 A"),
    (axes[1], "twist", 36.0, "Twist (deg)", "B-DNA ~36 deg"),
    (axes[2], "roll", 0.0, "Roll (deg)", "B-DNA ~0 deg"),
]:
    m = [ms(steps[k][param])[0] for k in labels]
    sd = [ms(steps[k][param])[1] for k in labels]
    ax.bar(xs, m, yerr=sd, capsize=3, color="#3b7dd8", alpha=0.85)
    ax.axhline(cryst, color="crimson", ls="--", lw=1.5, label=refname)
    ax.set_ylabel(ylab); ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
axes[2].set_xticks(xs); axes[2].set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
axes[2].set_xlabel("Base-pair step")
axes[0].set_title("1BNA Dickerson dodecamer (OL21/OPC, 50 ns) - helical step parameters vs B-DNA reference")
plt.tight_layout(); plt.savefig(f"{AN}/helical_per_step.png", dpi=130); plt.close()

# 2) RMSD timeseries
plt.figure(figsize=(9,4))
plt.plot(t, rmsd[:,1], lw=0.6, color="#2a6")
plt.axhline(rmsd[half:,1].mean(), color="k", ls="--", lw=1, label=f"2nd-half mean {rmsd[half:,1].mean():.2f} A")
plt.xlabel("Time (ns)"); plt.ylabel("Core backbone RMSD (A)")
plt.title("1BNA core RMSD vs equilibrated start (terminal bp excluded)")
plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
plt.savefig(f"{AN}/rmsd_core.png", dpi=130); plt.close()

# 3) RMSF per residue
rmsf = np.loadtxt(f"{AN}/rmsf.dat")
plt.figure(figsize=(9,4))
plt.bar(rmsf[:,0], rmsf[:,1], color="#d87", alpha=0.85)
plt.xlabel("Residue"); plt.ylabel("RMSF (A)")
plt.title("1BNA per-residue RMSF (terminal residues fray)")
plt.grid(axis="y", alpha=0.3); plt.tight_layout()
plt.savefig(f"{AN}/rmsf.png", dpi=130); plt.close()

print("\nPlots written: helical_per_step.png, rmsd_core.png, rmsf.png")

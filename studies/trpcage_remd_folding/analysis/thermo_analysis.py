#!/usr/bin/env python3
"""
Thermodynamic analysis of Trp-cage REMD:
- Folded fraction P_fold(T) from RMSD < 2.5 Å OR Q > 0.7
- Sigmoid fit → Tm
- Cv(T) from energy fluctuations
- 2D FEL at 300 K (RMSD vs Rg)
"""
import math, os, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

T_MIN, T_MAX, N_REP = 270.0, 600.0, 16
temps = np.array([T_MIN * math.exp(i * math.log(T_MAX / T_MIN) / (N_REP - 1)) for i in range(N_REP)])
temps[-1] = T_MAX

STUDY = "/home/hn533621/Portfolio/amber-md-agent/studies/trpcage_remd_folding"
BY_T = f"{STUDY}/analysis/by_temp"
PLOTS = f"{STUDY}/analysis/plots"
os.makedirs(PLOTS, exist_ok=True)

# ----- 1. Load per-replica data -----
data = {}
for i in range(N_REP):
    rmsd = np.loadtxt(f"{BY_T}/rmsd_{i:02d}.dat", comments="#")
    rg = np.loadtxt(f"{BY_T}/rg_{i:02d}.dat", comments="#")
    q = np.loadtxt(f"{BY_T}/q_{i:02d}.dat", comments="#")
    e2e = np.loadtxt(f"{BY_T}/e2e_{i:02d}.dat", comments="#")
    data[i] = {
        "T": temps[i],
        "rmsd": rmsd[:, 1],       # col 1 = RMSD
        "rg": rg[:, 1],           # col 1 = Rg
        "rg_max": rg[:, 2] if rg.shape[1] > 2 else None,
        "q_native": q[:, 1],      # col 1 = native contacts
        "q_nonnative": q[:, 2] if q.shape[1] > 2 else None,
        "e2e": e2e[:, 1],
    }

# Normalize Q to fraction (max possible at start = native count)
Q_NATIVE_MAX = data[0]["q_native"][0]  # frame 1 starts close to native
print(f"Q_native at frame 1 (slot 0, 270K): {Q_NATIVE_MAX:.1f} contacts")
print(f"Q_native max overall: {max(d['q_native'].max() for d in data.values()):.1f}")
Q_REF = max(d["q_native"].max() for d in data.values())
for d in data.values():
    d["q_frac"] = d["q_native"] / Q_REF

# Discard first 10% as burn-in for thermo averages
def keep(arr): return arr[len(arr)//10:]

# ----- 2. Folded fraction (multiple definitions) -----
P_fold_rmsd = []   # RMSD < 2.5 Å
P_fold_q    = []   # Q > 0.7
for i in range(N_REP):
    rmsd = keep(data[i]["rmsd"])
    q    = keep(data[i]["q_frac"])
    P_fold_rmsd.append(np.mean(rmsd < 2.5))
    P_fold_q.append(np.mean(q > 0.7))
P_fold_rmsd = np.array(P_fold_rmsd)
P_fold_q    = np.array(P_fold_q)

# Sigmoid fit (two-state Boltzmann)
def two_state(T, Tm, dH):
    """Two-state folding fraction. dH in kcal/mol, T in K."""
    R = 1.987e-3
    dG = dH * (1 - T/Tm)
    return 1.0 / (1.0 + np.exp(-dG / (R * T)))

# Restrict fit to physical range 270-460 K (above 460 K TIP3P unphysical)
mask = temps <= 460
try:
    popt_r, _ = curve_fit(two_state, temps[mask], P_fold_rmsd[mask],
                          p0=[330.0, 12.0], maxfev=5000)
    Tm_rmsd, dH_rmsd = popt_r
except Exception as e:
    print(f"RMSD sigmoid fit failed: {e}")
    Tm_rmsd, dH_rmsd = float("nan"), float("nan")
try:
    popt_q, _ = curve_fit(two_state, temps[mask], P_fold_q[mask],
                          p0=[330.0, 12.0], maxfev=5000)
    Tm_q, dH_q = popt_q
except Exception as e:
    print(f"Q sigmoid fit failed: {e}")
    Tm_q, dH_q = float("nan"), float("nan")

# ----- 3. Cv(T) from epot fluctuations (slot mdout AVERAGES) -----
# Parse epot mean and std from each replica's mdout
import re
Cv = []
E_mean = []
E_std = []
for i in range(N_REP):
    mdout = f"{STUDY}/simulations/remd_prod/remd_{i:02d}.mdout"
    eps = []
    with open(mdout) as f:
        for line in f:
            if "EPtot" in line:
                m = re.search(r"EPtot\s*=\s*([-\d.]+)", line)
                if m:
                    val = float(m.group(1))
                    eps.append(val)
    eps = np.array(eps)
    eps = eps[len(eps)//10:]  # burn-in
    mu = eps.mean()
    sd = eps.std()
    R = 1.987e-3
    cv = sd**2 / (R * temps[i]**2)   # kcal/mol/K
    Cv.append(cv)
    E_mean.append(mu)
    E_std.append(sd)
Cv = np.array(Cv)
E_mean = np.array(E_mean)
E_std = np.array(E_std)

# Tm from Cv peak (restricted to physical range)
mask_cv = (temps >= 280) & (temps <= 450)
Tm_cv = temps[mask_cv][np.argmax(Cv[mask_cv])]

# ----- 4. Write summary table -----
with open(f"{STUDY}/analysis/thermo_summary.dat", "w") as f:
    f.write("# T(K)  P_fold_RMSD<2.5  P_fold_Q>0.7  <Epot>(kcal/mol)  std_Epot  Cv(kcal/mol/K)  <Rg>(Å)\n")
    for i in range(N_REP):
        rg = keep(data[i]["rg"])
        f.write(f"{temps[i]:7.2f}  {P_fold_rmsd[i]:.4f}  {P_fold_q[i]:.4f}  "
                f"{E_mean[i]:12.2f}  {E_std[i]:8.2f}  {Cv[i]:8.4f}  {rg.mean():.3f}\n")

# ----- 5. Plots -----
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# P_fold vs T
ax = axes[0, 0]
ax.plot(temps, P_fold_rmsd, "o-", color="C0", label="RMSD < 2.5 Å")
ax.plot(temps, P_fold_q, "s-", color="C1", label="Q > 0.7")
if not np.isnan(Tm_rmsd):
    T_fit = np.linspace(270, 460, 200)
    ax.plot(T_fit, two_state(T_fit, Tm_rmsd, dH_rmsd), "--", color="C0",
            label=f"sigmoid fit (RMSD): Tm={Tm_rmsd:.1f} K, ΔH={dH_rmsd:.1f} kcal/mol")
if not np.isnan(Tm_q):
    ax.plot(T_fit, two_state(T_fit, Tm_q, dH_q), "--", color="C1",
            label=f"sigmoid fit (Q): Tm={Tm_q:.1f} K, ΔH={dH_q:.1f} kcal/mol")
ax.axvline(315, color="gray", ls=":", alpha=0.5, label="exp Tm ~315 K")
ax.axvline(460, color="red", ls=":", alpha=0.3, label="TIP3P limit")
ax.set_xlabel("Temperature (K)")
ax.set_ylabel("P_fold")
ax.set_title("Folded fraction vs T")
ax.legend(fontsize=8, loc="upper right")
ax.grid(alpha=0.3)

# Cv(T)
ax = axes[0, 1]
ax.plot(temps, Cv, "o-", color="C2")
ax.axvline(Tm_cv, color="red", ls="--", alpha=0.7, label=f"Cv peak: {Tm_cv:.1f} K")
ax.axvline(315, color="gray", ls=":", alpha=0.5, label="exp Tm ~315 K")
ax.axvline(460, color="red", ls=":", alpha=0.3, label="TIP3P limit")
ax.set_xlabel("Temperature (K)")
ax.set_ylabel("Cv (kcal/mol/K)")
ax.set_title("Heat capacity from <δE²>/kT²")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

# RMSD time series at 4 representative temps
ax = axes[1, 0]
for idx, label in [(0, "270 K"), (2, "300 K"), (4, "334 K"), (7, "392 K"), (15, "600 K")]:
    rmsd = data[idx]["rmsd"]
    t_ns = np.arange(len(rmsd)) * 0.010  # 10 ps/frame
    ax.plot(t_ns, rmsd, alpha=0.6, label=label, lw=0.7)
ax.axhline(2.5, color="black", ls="--", alpha=0.4, label="2.5 Å threshold")
ax.set_xlabel("Time (ns)")
ax.set_ylabel("RMSD vs 1L2Y (Å)")
ax.set_title("RMSD time series — select T")
ax.legend(fontsize=8, ncol=2)
ax.grid(alpha=0.3)

# 2D FEL at 300 K (RMSD vs Rg)
ax = axes[1, 1]
i_300 = 2   # T = 300.3 K closest to 300
rmsd_300 = keep(data[i_300]["rmsd"])
rg_300   = keep(data[i_300]["rg"])
H, xe, ye = np.histogram2d(rmsd_300, rg_300, bins=50)
H = H.T
P = H / H.sum()
F = -1.987e-3 * temps[i_300] * np.log(P + 1e-12)
F -= F[P > 0].min()
F[P == 0] = np.nan
im = ax.imshow(F, origin="lower",
               extent=[xe[0], xe[-1], ye[0], ye[-1]],
               aspect="auto", cmap="viridis_r", vmin=0, vmax=4)
plt.colorbar(im, ax=ax, label="ΔG (kcal/mol)")
ax.set_xlabel("RMSD vs 1L2Y (Å)")
ax.set_ylabel("Rg (Å)")
ax.set_title(f"2D FEL at T = {temps[i_300]:.1f} K")

plt.tight_layout()
plt.savefig(f"{PLOTS}/thermodynamics.png", dpi=150)
plt.close()

# ----- 6. Print summary to stdout -----
print("=" * 70)
print(f"Trp-cage REMD thermodynamics summary")
print("=" * 70)
print(f"{'T (K)':>8} {'P_fold(RMSD)':>14} {'P_fold(Q)':>10} {'<Epot>':>14} {'Cv':>10}")
for i in range(N_REP):
    print(f"{temps[i]:8.1f} {P_fold_rmsd[i]:14.3f} {P_fold_q[i]:10.3f} "
          f"{E_mean[i]:14.1f} {Cv[i]:10.4f}")
print()
print(f"Tm from RMSD sigmoid:  {Tm_rmsd:.1f} K  (ΔH = {dH_rmsd:.1f} kcal/mol)")
print(f"Tm from Q sigmoid:     {Tm_q:.1f} K  (ΔH = {dH_q:.1f} kcal/mol)")
print(f"Tm from Cv peak:       {Tm_cv:.1f} K")
print(f"Experimental Tm (Neidigh 2002): ~315 K")
print(f"\nOutput: {STUDY}/analysis/thermo_summary.dat")
print(f"Plot:   {PLOTS}/thermodynamics.png")

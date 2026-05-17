"""WHAM/MBAR PMF analysis for trypsin-benzamidine US.
Uses MBAR weights + histogram binning. Bootstrap for uncertainty.
Standard-state correction via volume-integral of bound basin."""
import numpy as np
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pymbar import MBAR, timeseries

ROOT = "/home/hn533621/Portfolio/amber-md-agent-improvements/studies/trypsin_benzamidine"
US_DIR = f"{ROOT}/simulations/us"
ANA_DIR = f"{ROOT}/analysis"
os.makedirs(ANA_DIR, exist_ok=True)

T  = 300.0
kT = 0.0019872041 * T
K_AMBER = 10.0
WINDOW_CENTERS = np.arange(3.0, 17.5, 0.5)
N_WIN = len(WINDOW_CENTERS)
NEQ_DISCARD = 1000   # first 1000 dumps (1 ns) discarded for safety

print(f"T={T} K  kT={kT:.4f} kcal/mol  K_amber={K_AMBER}  windows={N_WIN}")

# Load samples
r_list = []
N_k = np.zeros(N_WIN, dtype=int)
for k, r0 in enumerate(WINDOW_CENTERS):
    wname = f"w{r0:.2f}".replace(".", "_")
    path = f"{US_DIR}/{wname}/prod_dist.dat"
    d = np.loadtxt(path)
    r = d[:, 1]
    r = r[NEQ_DISCARD:]
    # uncorrelated subsample
    g = timeseries.statistical_inefficiency(r)
    idx = np.arange(0, len(r), max(int(np.ceil(g)), 1))
    r_sub = r[idx]
    r_list.append(r_sub)
    N_k[k] = len(r_sub)
    print(f"  win {r0:.2f}: kept={len(r)}  g={g:.1f}  N_sub={N_k[k]}  <r>={r_sub.mean():.2f}")

r_all = np.concatenate(r_list)
N_total = N_k.sum()
print(f"\nTotal samples: {N_total}")

# u_kn[k,n] = beta * U_k(x_n) for sample n in window k bias
u_kn = np.zeros((N_WIN, N_total))
for k, r0 in enumerate(WINDOW_CENTERS):
    u_kn[k, :] = K_AMBER * (r_all - r0)**2 / kT

print("Running MBAR ...")
mbar = MBAR(u_kn, N_k)

# Add unbiased state (K+1) as extra column, get weights under it
u_kn_ext = np.zeros((N_WIN + 1, N_total))
u_kn_ext[:N_WIN] = u_kn
N_k_ext = np.concatenate([N_k, [0]])
mbar_ext = MBAR(u_kn_ext, N_k_ext)
W_mat = mbar_ext.weights()      # shape (N_total, N_WIN+1)
w_unbiased = W_mat[:, N_WIN]
w_unbiased = w_unbiased / w_unbiased.sum()

# Bin into PMF
r_min, r_max, dr = 2.8, 17.5, 0.1
r_edges = np.arange(r_min, r_max + dr, dr)
r_centers = (r_edges[:-1] + r_edges[1:]) / 2
n_bins = len(r_centers)

def pmf_from_weights(r_samples, w_samples):
    p = np.zeros(n_bins)
    for i in range(n_bins):
        m = (r_samples >= r_edges[i]) & (r_samples < r_edges[i + 1])
        p[i] = w_samples[m].sum()
    # Add tiny floor to avoid log(0)
    p = np.where(p > 0, p, p[p > 0].min() * 1e-3)
    pmf = -kT * np.log(p)
    pmf -= pmf.min()
    return pmf

pmf = pmf_from_weights(r_all, w_unbiased)

# Bootstrap uncertainty
N_BOOT = 50
boot_pmfs = []
np.random.seed(42)
for b in range(N_BOOT):
    # Resample each window
    r_boot_list = []
    for k in range(N_WIN):
        idx = np.random.randint(0, N_k[k], N_k[k])
        r_boot_list.append(r_list[k][idx])
    r_b = np.concatenate(r_boot_list)
    u_kn_b = np.zeros((N_WIN + 1, N_total))
    for k, r0 in enumerate(WINDOW_CENTERS):
        u_kn_b[k, :] = K_AMBER * (r_b - r0)**2 / kT
    try:
        mbar_b = MBAR(u_kn_b, N_k_ext, verbose=False)
        w_b = mbar_b.weights()[:, N_WIN]
        w_b = w_b / w_b.sum()
        boot_pmfs.append(pmf_from_weights(r_b, w_b))
    except Exception as e:
        print(f"  boot {b}: failed {e}")
        continue
boot_pmfs = np.array(boot_pmfs)
pmf_err = boot_pmfs.std(axis=0)
print(f"Bootstrap: {len(boot_pmfs)} successful")

# Shift so bulk plateau = 0
mask_bulk = (r_centers >= 13.0) & (r_centers <= 17.0)
W_bulk_mean = pmf[mask_bulk].mean()
W = pmf - W_bulk_mean
W_min = W.min()
r_at_min = r_centers[np.argmin(W)]
print(f"\nPMF features:")
print(f"  PMF minimum: {W_min:.2f} kcal/mol  at r={r_at_min:.2f} A")
print(f"  Bulk plateau (mean over 13-17 A): 0.00 (shifted)")

# Standard-state correction (volume integral of bound state)
# ΔG_bind° = -kT ln[ C° * ∫_bound exp(-W(r)/kT) * 4π r^2 dr ]
# C° = 1 M = 1/1660.539 A^-3
C0 = 1.0 / 1660.539
mask_bound = (r_centers >= 6.0) & (r_centers <= 9.0)
W_bound = W[mask_bound]
r_bound = r_centers[mask_bound]
Z_bound = np.trapezoid(np.exp(-W_bound / kT) * 4 * np.pi * r_bound**2, r_bound)
dG_bind = -kT * np.log(C0 * Z_bound)
print(f"  Z_bound (Å³)   = {Z_bound:.4f}")
print(f"  ΔG_bind        = {dG_bind:.2f} kcal/mol")
print(f"  Experimental   = -6.4 kcal/mol (Ki=18 µM, Talhout & Engberts 2001)")

# Save
np.savetxt(f"{ANA_DIR}/pmf.dat",
           np.column_stack([r_centers, W, pmf_err]),
           header="r(A)  PMF(kcal/mol)  err(kcal/mol)", fmt="%.4f")

fig, ax = plt.subplots(figsize=(7, 4.5))
ax.errorbar(r_centers, W, yerr=pmf_err, fmt="-", lw=1.5, color="C0", label="PMF")
ax.axhline(0, color="k", lw=0.5, ls=":")
ax.axvspan(6.0, 9.0, alpha=0.12, color="C2", label="bound basin (Z integral)")
ax.axvspan(13.0, 17.0, alpha=0.12, color="C3", label="bulk plateau (W=0)")
ax.axhline(W_min, color="C0", lw=0.5, ls="--")
ax.set_xlabel("r (BEN_COM – Asp189-Cα) / Å")
ax.set_ylabel("PMF (kcal/mol)")
ax.set_title(
    f"Trypsin–benzamidine PMF (US, 29 win × 10 ns, ff14SB/GAFF2/TIP3P)\n"
    f"PMF_min = {W_min:.2f} kcal/mol   ΔG_bind° = {dG_bind:.2f} kcal/mol   (exp = -6.4)"
)
ax.legend(loc="lower right")
ax.set_xlim(r_min, r_max)
plt.tight_layout()
plt.savefig(f"{ANA_DIR}/pmf.png", dpi=150)
print(f"\nSaved: {ANA_DIR}/pmf.dat , {ANA_DIR}/pmf.png")

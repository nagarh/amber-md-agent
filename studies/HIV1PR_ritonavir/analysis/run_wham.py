"""
WHAM (Weighted Histogram Analysis Method) for umbrella sampling PMF.
Grossfield, A. WHAM: An Implementation of the Weighted Histogram Analysis Method.
http://membrane.urmc.rochester.edu/content/wham

Reads dist.dat files from each umbrella window and computes PMF via WHAM iteration.
"""
import numpy as np
import os
import glob

# ── Parameters ─────────────────────────────────────────────────────────────────
WINDIR    = os.path.join(os.path.dirname(__file__), '..', 'simulations', 'windows')
OUTDIR    = os.path.dirname(__file__)
TEMP      = 300.0          # K
KB        = 0.001987204    # kcal/mol/K
KBT       = KB * TEMP
K_BIAS    = 3.0            # kcal/mol/A^2 — force constant used in umbrella
XI_MIN    = 4.0            # A — histogram range
XI_MAX    = 32.0           # A
N_BINS    = 140            # 0.2 A bin width
EQUIL_PS  = 500            # ps to discard as equilibration (500 ps = 250000 steps / dump every 500)
EQUIL_FRAMES = EQUIL_PS    # dist.dat written every 500 steps * 0.002 ps = 1 ps per frame

# ── Load data ──────────────────────────────────────────────────────────────────
windows = sorted(glob.glob(os.path.join(WINDIR, 'w*/dist.dat')))
print(f"Found {len(windows)} dist.dat files")

centers  = []
data_all = []

for dat_file in windows:
    wname = os.path.basename(os.path.dirname(dat_file))
    # Parse window center from directory name: w05p5 -> 5.5
    center = float(wname[1:].replace('p', '.'))
    
    try:
        raw = np.loadtxt(dat_file, usecols=1)  # col 1 = actual distance
    except Exception as e:
        print(f"  SKIP {wname}: {e}")
        continue
    
    # Discard equilibration frames
    data = raw[EQUIL_FRAMES:]
    if len(data) < 100:
        print(f"  SKIP {wname}: only {len(data)} frames after equilibration")
        continue
    
    centers.append(center)
    data_all.append(data)
    print(f"  {wname}: center={center:.1f} A, {len(data)} frames, "
          f"mean={np.mean(data):.2f} A, std={np.std(data):.2f} A")

N_WIN = len(centers)
centers = np.array(centers)
print(f"\nUsing {N_WIN} windows for WHAM")

# ── Build histograms ───────────────────────────────────────────────────────────
bins   = np.linspace(XI_MIN, XI_MAX, N_BINS + 1)
xi     = 0.5 * (bins[:-1] + bins[1:])   # bin centers
dxi    = xi[1] - xi[0]

hist = np.zeros((N_WIN, N_BINS))
for i, data in enumerate(data_all):
    h, _ = np.histogram(data, bins=bins)
    hist[i] = h

N_i   = hist.sum(axis=1)          # total counts per window
N_tot = hist.sum()

# ── WHAM iteration ─────────────────────────────────────────────────────────────
# Bias energy for each window at each bin center
# U_i(xi) = 0.5 * K * (xi - center_i)^2
U_bias = 0.5 * K_BIAS * (xi[np.newaxis, :] - centers[:, np.newaxis])**2  # (N_WIN, N_BINS)

f_i    = np.zeros(N_WIN)   # free energy offsets (iterate to convergence)
tol    = 1e-6
max_iter = 100000

print("\nRunning WHAM iterations...")
for it in range(max_iter):
    # Unnormalized density
    # rho(xi) = sum_i hist_i(xi) / sum_i N_i * exp(f_i - U_i(xi)/kBT)
    denom  = np.sum(N_i[:, np.newaxis] * np.exp(f_i[:, np.newaxis] - U_bias / KBT), axis=0)
    
    # Avoid division by zero
    denom  = np.where(denom > 0, denom, 1e-300)
    
    rho    = hist.sum(axis=0) / denom  # unbiased density (unnormalized)
    
    # Update f_i
    f_new  = -KBT * np.log(np.sum(rho[np.newaxis, :] * np.exp(-U_bias / KBT) * dxi, axis=1))
    
    # Shift so f_0 = 0
    f_new -= f_new[0]
    
    delta  = np.max(np.abs(f_new - f_i))
    f_i    = f_new
    
    if (it + 1) % 1000 == 0:
        print(f"  iter {it+1}: max delta = {delta:.2e}")
    
    if delta < tol:
        print(f"  Converged at iter {it+1}: delta = {delta:.2e}")
        break

# ── Compute PMF ────────────────────────────────────────────────────────────────
denom  = np.sum(N_i[:, np.newaxis] * np.exp(f_i[:, np.newaxis] - U_bias / KBT), axis=0)
denom  = np.where(denom > 0, denom, 1e-300)
rho    = hist.sum(axis=0) / denom

# Mask bins with no data
mask   = hist.sum(axis=0) > 0
pmf    = np.full(N_BINS, np.nan)
pmf[mask] = -KBT * np.log(np.where(rho[mask] > 0, rho[mask], 1e-300))

# Set minimum to zero
min_pmf = np.nanmin(pmf)
pmf    -= min_pmf

# ── Save output ────────────────────────────────────────────────────────────────
outfile = os.path.join(OUTDIR, 'pmf.dat')
with open(outfile, 'w') as f:
    f.write("# WHAM PMF: HIV-1 PR ritonavir unbinding\n")
    f.write("# T=300K, k=3.0 kcal/mol/A^2, 50 windows, 0.5A spacing\n")
    f.write("# Column 1: COM distance (A)\n")
    f.write("# Column 2: PMF (kcal/mol)\n")
    for xi_i, pmf_i in zip(xi, pmf):
        if not np.isnan(pmf_i):
            f.write(f"{xi_i:.3f}  {pmf_i:.4f}\n")

print(f"\nPMF written to {outfile}")
print(f"PMF range: 0.0 to {np.nanmax(pmf):.2f} kcal/mol")
print(f"Binding free energy estimate: {np.nanmax(pmf):.2f} kcal/mol")

#!/usr/bin/env python3
"""
Analyze TI results: extract DV/DL, integrate, compute ΔΔGbind.

Usage:
  python analyze_ti.py bound   # bound leg
  python analyze_ti.py apo     # apo leg
  python analyze_ti.py final   # compute ΔΔGbind from both legs
"""
import sys, os, re, math
import numpy as np

STUDY  = "/home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI"
LAMBDAS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

def parse_dvdl(mdout_path):
    """Extract DV/DL values from TI mdout file."""
    dvdl_values = []
    with open(mdout_path) as f:
        for line in f:
            if 'DV/DL  =' in line:
                val = float(line.split('=')[1].strip().split()[0])
                dvdl_values.append(val)
    if not dvdl_values:
        raise ValueError(f"No DV/DL found in {mdout_path}")
    # Discard first 20% as additional equilibration
    n_eq = len(dvdl_values) // 5
    dvdl_prod = dvdl_values[n_eq:]
    mean = np.mean(dvdl_prod)
    sem  = np.std(dvdl_prod) / math.sqrt(len(dvdl_prod))
    return mean, sem, len(dvdl_prod)

def trapezoid_integrate(lambdas, means, sems):
    """Trapezoidal integration of <DV/DL> vs lambda."""
    dg = 0.0
    var = 0.0
    for i in range(len(lambdas) - 1):
        dl = lambdas[i+1] - lambdas[i]
        dg  += dl * (means[i] + means[i+1]) / 2.0
        var += (dl/2)**2 * (sems[i]**2 + sems[i+1]**2)
    return dg, math.sqrt(var)

def analyze_leg(leg):
    """Analyze one TI leg (bound or apo). Returns (dG, dG_err)."""
    leg_dir = f"{STUDY}/simulations/ti_{leg}"
    means, sems = [], []

    print(f"\n{'='*60}")
    print(f"TI {leg.upper()} LEG")
    print(f"{'='*60}")
    print(f"{'λ':>6}  {'<DV/DL>':>12}  {'SEM':>10}  {'N frames':>10}")

    for lam in LAMBDAS:
        lam_str = f"{lam:.1f}"
        # Try prod mdout first, then equil
        mdout = f"{leg_dir}/lambda_{lam_str}/prod.mdout"
        if not os.path.exists(mdout):
            print(f"  λ={lam_str}: MISSING {mdout}")
            means.append(None)
            sems.append(None)
            continue
        try:
            mean, sem, n = parse_dvdl(mdout)
            means.append(mean)
            sems.append(sem)
            print(f"  {lam_str:>6}  {mean:>12.4f}  {sem:>10.4f}  {n:>10d}")
        except Exception as e:
            print(f"  λ={lam_str}: ERROR {e}")
            means.append(None)
            sems.append(None)

    # Filter out missing windows
    valid = [(l, m, s) for l, m, s in zip(LAMBDAS, means, sems)
             if m is not None]
    if len(valid) < len(LAMBDAS):
        print(f"\nWARNING: {len(LAMBDAS)-len(valid)} windows missing!")
    if len(valid) < 3:
        raise ValueError("Fewer than 3 valid windows — cannot integrate")

    lams_v, means_v, sems_v = zip(*valid)
    dg, dg_err = trapezoid_integrate(list(lams_v), list(means_v), list(sems_v))

    print(f"\nΔGmut,{leg} = {dg:.3f} ± {dg_err:.3f} kcal/mol")
    print(f"({len(valid)}/{len(LAMBDAS)} windows)")
    return dg, dg_err

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'final'

    if mode == 'bound':
        analyze_leg('bound')
    elif mode == 'apo':
        analyze_leg('apo')
    elif mode == 'final':
        dg_bound, err_bound = analyze_leg('bound')
        dg_apo,   err_apo   = analyze_leg('apo')
        ddg     = dg_bound - dg_apo
        ddg_err = math.sqrt(err_bound**2 + err_apo**2)

        print(f"\n{'='*60}")
        print(f"RESULT: ΔΔGbind (T315I - WT)")
        print(f"{'='*60}")
        print(f"  ΔGmut,bound = {dg_bound:+.3f} ± {err_bound:.3f} kcal/mol")
        print(f"  ΔGmut,apo   = {dg_apo:+.3f} ± {err_apo:.3f} kcal/mol")
        print(f"  ΔΔGbind     = {ddg:+.3f} ± {ddg_err:.3f} kcal/mol")
        print(f"  (positive = T315I binds imatinib LESS tightly)")
        print(f"  Experimental: ~+2.7 kcal/mol (100-fold Kd loss)")

        # Write result to file
        result_file = f"{STUDY}/analysis/ddg_result.txt"
        with open(result_file, 'w') as f:
            f.write(f"ΔΔGbind (T315I - WT) TI result\n")
            f.write(f"System: ABL1 kinase + imatinib\n")
            f.write(f"Mutation: T315I (gatekeeper)\n\n")
            f.write(f"ΔGmut,bound = {dg_bound:+.3f} ± {err_bound:.3f} kcal/mol\n")
            f.write(f"ΔGmut,apo   = {dg_apo:+.3f} ± {err_apo:.3f} kcal/mol\n")
            f.write(f"ΔΔGbind     = {ddg:+.3f} ± {ddg_err:.3f} kcal/mol\n")
            f.write(f"Experimental (100-fold Kd loss): +2.7 kcal/mol\n")
        print(f"\nResult written to {result_file}")
    else:
        print(f"Unknown mode: {mode}. Use: bound, apo, or final")
        sys.exit(1)

if __name__ == '__main__':
    main()

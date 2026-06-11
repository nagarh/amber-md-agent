# Skill: amber-gamd (Gaussian Accelerated MD)

GaMD adds a harmonic boost potential to the system PES, smoothed via Gaussian distribution → accurate cumulant-expansion reweighting. Single-replica enhanced sampling (vs REMD multi-replica).

Validated on alanine dipeptide (explicit solvent) and protein systems.

---

## When to Use
- Single-replica enhanced sampling (cheaper than REMD)
- Conformational sampling over ns-µs timescales
- Ligand binding (LiGaMD, igamd=10/11)
- Peptide-protein binding (Pep-GaMD, igamd=14/15/18)
- Protein-protein interactions (PPI-GaMD, igamd=16/17)
- Any system with intermediate barriers (3-15 kcal/mol; range per Miao et al. JCTC 2015)

NOT for high barriers (>20 kcal/mol; per Miao et al. JCTC 2015) — boost won't help, use metadynamics.

For full igamd mode list → `rag_query("GaMD igamd modes dual total dihedral boost")`. Most studies use **igamd=3** (dual boost: dihedral + total), but justify the boost mode per study via the tier protocol → `rag_query("GaMD igamd boost mode recommended dual dihedral total system")` / lit precedent (Miao et al. JCTC 2015).

---

## Working mdin template (igamd=3 dual boost)

**Before filling this template, RAG-query phase lengths for your system:**
```
rag_query("GaMD ntcmd nteb ntave phase length recommended system size protein ligand")
rag_query("GaMD sigma0P sigma0D boost threshold recommended")
```

```
&cntrl
   imin=0, irest=1, ntx=5,
   nstlim=<rag: total steps = ntcmdprep+ntcmd+ntebprep+nteb+production>,
   dt=0.002,
   ntb=2, ntp=1, taup=<rag/justify per study: "GaMD barostat pressure coupling taup recommended">, pres0=1.0,
   cut=<rag: "GaMD cutoff PME recommended">,
   ntc=2, ntf=2,
   ntt=3, gamma_ln=<rag: "GaMD Langevin collision frequency gamma_ln recommended">, ig=-1, temp0=<rag: "GaMD production temperature temp0 recommended"; justify per study via tier protocol>,
   ntpr=<benchmark-mode default 5000; per CLAUDE.md storage-conservative defaults>, ntwx=<rag: "GaMD ntwx trajectory frequency">, ntwr=<benchmark-mode default 50000; per CLAUDE.md storage-conservative defaults>, ioutfm=1,
   igamd=3, iE=1, irest_gamd=0,
   ntcmd=<rag: "GaMD ntcmd conventional MD phase length convergence">,
   ntcmdprep=<ntcmd/10, must be multiple of ntave>,
   nteb=<rag: "GaMD nteb boost equilibration phase length">,
   ntebprep=<nteb/20, must be multiple of ntave>,
   ntave=<rag: "GaMD ntave averaging interval recommended">,
   sigma0P=<rag: "GaMD sigma0P sigma0D threshold total dihedral boost">,
   sigma0D=<rag: "GaMD sigma0D dihedral boost threshold">,
&end
```

**Parameter framing:** `dt=0.002` (2 fs) is gated by the REQUIRED `ntc=2`/SHAKE H-bond constraints — confirm per study; drop to 0.001 if SHAKE is off. `ntb=2, ntp=1` are the REQUIRED NPT-ensemble pairing (constant-pressure box) and `pres0=1.0` is the physical 1 atm condition (fixed). `taup` is a tunable barostat coupling constant — justify per study via the tier protocol.

Phases: cMD (ntcmdprep→ntcmd) → boost no stats (ntebprep) → boost+update (nteb) → production.

**CRITICAL:** ntcmdprep, ntcmd, ntebprep, nteb MUST all be multiples of ntave — else crash.

Typical scale (NOT defaults — verify with RAG for your system):
- Small peptide in water: ntcmd~50k, nteb~100k, ntave~10k
- Protein (100-300 res): ntcmd~200k, nteb~400k, ntave~20k  
- Protein-ligand: ntcmd~500k, nteb~1M, ntave~50k

---

## Submit (single GPU)
```bash
pmemd.cuda -O -i gamd.in -p system.prmtop -c equil.rst7 \
    -o gamd.out -r gamd.rst7 -x gamd.nc -inf gamd.mdinfo \
    -gamd gamd.log
```
The `-gamd <file>` flag is **REQUIRED** — boost log saved per ntwx frames.

GPU MPI also works (pmemd.cuda.MPI). NOT in sander.

**For Pep/Li/PPI-GaMD: serial pmemd.cuda ONLY (not .MPI)**

---

## gamd.log format
8 columns (space-separated): ntwx, total_nstep, Unboosted-PE, Unboosted-Dih, Total-Force-Weight, Dih-Force-Weight, Boost-Energy-Total (ΔV_total), Boost-Energy-Dih (ΔV_dih).

Total dual boost: column 7 + column 8.

**Alignment with trajectory:** gamd.log entries correspond to frames at step = column 2. Match via step number, NOT row index — log starts AFTER ntcmd, traj starts from step ntwx.

```python
for j, s in enumerate(nstep_log):
    idx = s//ntwx - 1   # 0-indexed traj frame
    if 0 <= idx < n_frames:
        boost_aligned[idx] = boost[j]
```

---

## Reweighting (cumulant expansion 2nd order)

```
F(s) = -kT·ln P_biased(s) - (⟨ΔV⟩_s - β·Var(ΔV)_s / 2)
```

**Validity check:** σ_V should be < 10 kcal/mol (cumulant-expansion validity cutoff per Miao et al. JCTC 2015 / PyReweighting docs). If σ_V > 10, cumulant expansion breaks down → use Maclaurin or full exp reweighting (PyReweighting).

Discard frames before ntcmd+nteb steps for production analysis.

---

## Validation result
- Alanine dipeptide ff14SB+TIP3P
- 4 ns production after 1.2 ns warmup
- Reweighted PMF global min @ phi=-135°, psi=+165° (C5/PPII) → matches lit.
- αL/C7ax not sampled in 4 ns at sigma0=6 → barrier > boost
- Throughput: ~400 ns/day on RTX A6000 for ~700-atom solvated peptide

## Gotchas
- ntcmdprep/ntcmd/ntebprep/nteb must all be MULTIPLES of ntave (else crash)
- sigma0P/sigma0D control the boost/reweighting tradeoff: higher (e.g. ~6) is conservative (cleaner reweighting), lower (e.g. ~4) increases boost but degrades reweighting. Justify per study via the tier protocol → `rag_query("GaMD sigma0P sigma0D threshold total dihedral boost recommended")` / lit precedent (Miao et al. JCTC 2015), matching the `<rag:...>` placeholders in the mdin template above
- irest_gamd=0 means freeze E,k0 after equilibration; =1 reads from gamd-restart.dat
- Restart from production: must have gamd-restart.dat in cwd; set irest_gamd=1
- NOT compatible with REMD (-rem 1) — single replica only
- For triple/Pep/Li/PPI-GaMD: only serial pmemd.cuda (not .MPI)
- **Small / low-barrier systems over-boost at sigma0P=sigma0D=6** → large ⟨ΔV⟩ and ΔV/kT, making the 2nd-order cumulant reweight unreliable. For small/low-barrier systems use a smaller σ0 (≈2–3), dihedral-only boost (`igamd=2`), or much longer sampling. **Check ΔV/kT ≲ 10 before trusting the reweighted PMF** — tune σ0 down until it does.

## References
- Miao et al. JCTC 2015, DOI:10.1021/acs.jctc.5b00436 (GaMD theory)
- Wang et al. JCTC 2021 (LiGaMD3)
- Amber 24 manual §24.3 (pages 478-485)
- PyReweighting code: http://miao.compbio.ku.edu/GaMD

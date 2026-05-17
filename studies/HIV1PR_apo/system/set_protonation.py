#!/usr/bin/env python3
"""Rename residues to set protonation states for HIV-1 protease at pH 5.5:
- Chain A ASP25 → ASH (catalytic dyad: one ASP protonated, mono-protonated state)
- Chain B ASP25 stays ASP
- HIS69 both chains → HIP (pH 5.5 < pKa His ~6 → fully protonated)
"""
from pathlib import Path

INP = Path("studies/HIV1PR_apo/system/1HHP_dimer.pdb")
OUT = Path("studies/HIV1PR_apo/system/1HHP_dimer_proto.pdb")

renames = {
    ("A", 25): "ASH",
    ("A", 69): "HIP",
    ("B", 69): "HIP",
}

out_lines = []
n_renamed = 0
for line in INP.read_text().splitlines():
    if line.startswith(("ATOM", "HETATM")):
        try:
            chain = line[21]
            resnum = int(line[22:26].strip())
            key = (chain, resnum)
            if key in renames:
                new_resname = renames[key]
                line = line[:17] + f"{new_resname:>3s}" + line[20:]
                n_renamed += 1
        except (ValueError, IndexError):
            pass
    out_lines.append(line)
OUT.write_text("\n".join(out_lines) + "\n")
print(f"Wrote {OUT}  ({n_renamed} atom lines renamed)")

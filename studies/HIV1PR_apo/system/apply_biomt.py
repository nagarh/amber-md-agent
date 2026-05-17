#!/usr/bin/env python3
"""Apply REMARK 350 BIOMT operators to build biological dimer for HIV-1 protease.
Reads 1HHP chain A, applies BIOMT op 2 to produce chain B, writes combined PDB."""
import numpy as np
from pathlib import Path

INP = Path("studies/HIV1PR_apo/raw_pdbs/1HHP.pdb")
OUT = Path("studies/HIV1PR_apo/system/1HHP_dimer.pdb")

# BIOMT op 2 for 1HHP (from REMARK 350)
R = np.array([
    [0.0, 1.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.0, 0.0, -1.0],
])
T = np.array([0.0, 0.0, 0.0])

atom_lines = []
for line in INP.read_text().splitlines():
    if line.startswith(("ATOM", "HETATM", "TER")):
        atom_lines.append(line)
    elif line.startswith("END"):
        break

dimer_lines = []
serial = 1
for line in atom_lines:
    if line.startswith(("ATOM", "HETATM")):
        new_line = line[:6] + f"{serial:>5d}" + line[11:]
        dimer_lines.append(new_line)
        serial += 1
    elif line.startswith("TER"):
        dimer_lines.append(line)

dimer_lines.append("TER\n".strip())

# Apply BIOMT op 2 → chain B
for line in atom_lines:
    if line.startswith(("ATOM", "HETATM")):
        x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
        new = R @ np.array([x, y, z]) + T
        new_line = (
            line[:6] + f"{serial:>5d}" + line[11:21] + "B" + line[22:30]
            + f"{new[0]:8.3f}{new[1]:8.3f}{new[2]:8.3f}" + line[54:]
        )
        dimer_lines.append(new_line)
        serial += 1

dimer_lines.append("TER")
dimer_lines.append("END")

OUT.write_text("\n".join(dimer_lines) + "\n")
print(f"Written: {OUT}  ({serial-1} atoms)")

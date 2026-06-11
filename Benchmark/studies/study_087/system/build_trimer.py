#!/usr/bin/env python
"""Build OmpF biological trimer from 2OMF asymmetric unit (1 chain) by applying
the 3 REMARK 350 BIOMT operators. Strips C8E detergent and waters; protein only."""
import numpy as np

RAW = "/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/raw_pdbs/2OMF.pdb"
OUT = "/data/hn533621/Portfolio/amber-md-agent-general/Benchmark/studies/study_087/system/trimer.pdb"

# BIOMT operators from REMARK 350 of 2OMF (R 3x3, T 3-vector)
ops = [
    (np.eye(3), np.zeros(3)),
    (np.array([[-0.500000, -0.866025, 0.0],
               [ 0.866025, -0.500000, 0.0],
               [ 0.0,       0.0,      1.0]]),
     np.array([59.25000, 102.62401, 0.0])),
    (np.array([[-0.500000,  0.866025, 0.0],
               [-0.866025, -0.500000, 0.0],
               [ 0.0,       0.0,      1.0]]),
     np.array([-59.25000, 102.62401, 0.0])),
]

# Read protein ATOM records only (drop HETATM C8E and HOH)
atoms = []
with open(RAW) as f:
    for line in f:
        if line.startswith("ATOM"):
            resname = line[17:20].strip()
            if resname == "HOH":
                continue
            atoms.append(line.rstrip("\n"))

print(f"Protein ATOM records in monomer: {len(atoms)}")

chain_ids = ["A", "B", "C"]
out_lines = []
serial = 1
for ci, (R, T) in enumerate(ops):
    cid = chain_ids[ci]
    for line in atoms:
        x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
        xyz = np.array([x, y, z])
        nx, ny, nz = R @ xyz + T
        newline = (line[:21] + cid + line[22:30]
                   + f"{nx:8.3f}{ny:8.3f}{nz:8.3f}" + line[54:])
        newline = "ATOM  " + f"{serial:5d}" + newline[11:]
        out_lines.append(newline)
        serial += 1
    out_lines.append("TER")

with open(OUT, "w") as f:
    f.write("\n".join(out_lines) + "\n")

print(f"Wrote trimer to {OUT}")
print(f"Total atoms: {serial-1}  ({(serial-1)//3} per chain)")

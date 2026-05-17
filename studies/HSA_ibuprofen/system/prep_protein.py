#!/usr/bin/env python3
"""
Rename residues in chain A protein_only.pdb for Amber:
- CYS in disulfide pairs → CYX
- HIS → HID (default neutral)
- HIS 9 → HIP (propka3 pKa 7.83 > 7.4)
- GLU 244 → GLH (propka3 pKa 8.53 > 7.4, buried)
Output: protein_clean.pdb
"""
import sys

DISULF_CYS = {
    53, 62, 75, 91, 90, 101, 124, 169, 168, 177, 200, 246, 245, 253,
    265, 279, 278, 289, 316, 361, 360, 369, 392, 438, 437, 448, 461,
    477, 476, 487, 514, 559, 558, 567
}

inp = "studies/HSA_ibuprofen/system/protein_only.pdb"
out = "studies/HSA_ibuprofen/system/protein_clean.pdb"

out_lines = []
stats = {"CYX": 0, "HID": 0, "HIP": 0, "GLH": 0}

with open(inp) as f:
    for line in f:
        if line[:4] not in ("ATOM", "TER "):
            out_lines.append(line)
            continue
        if line[:4] != "ATOM":
            out_lines.append(line)
            continue

        resname = line[17:20].strip()
        resnum  = int(line[22:26].strip())

        if resname == "CYS" and resnum in DISULF_CYS:
            line = line[:17] + "CYX" + line[20:]
            stats["CYX"] += 1
        elif resname == "HIS":
            if resnum == 9:
                line = line[:17] + "HIP" + line[20:]
                stats["HIP"] += 1
            else:
                line = line[:17] + "HID" + line[20:]
                stats["HID"] += 1
        elif resname == "GLU" and resnum == 244:
            line = line[:17] + "GLH" + line[20:]
            stats["GLH"] += 1

        out_lines.append(line)

with open(out, "w") as f:
    f.writelines(out_lines)

print(f"Written: {out}")
for k, v in stats.items():
    print(f"  {k}: {v} atoms renamed")

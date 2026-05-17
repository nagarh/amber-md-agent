"""Apply non-default protonation: HIS57 -> HID (catalytic triad H-bond to Asp102).
All other HIS default (ff14SB default = HIE)."""
import sys

inp = "studies/trypsin_benzamidine/system/protein_only.pdb"
out = "studies/trypsin_benzamidine/system/protein_protonated.pdb"

lines = open(inp).readlines()
new = []
for l in lines:
    if l.startswith("ATOM") and l[17:20].strip() == "HIS":
        resnum = l[22:26].strip()
        if resnum == "57":
            l = l[:17] + "HID" + l[20:]
        else:
            l = l[:17] + "HIE" + l[20:]
    new.append(l)
open(out, "w").writelines(new)
print(f"Wrote {out}")
import subprocess
r = subprocess.run(["grep", "-c", "HID", out], capture_output=True, text=True)
print(f"HID atoms: {r.stdout.strip()}")
r = subprocess.run(["grep", "-c", "HIE", out], capture_output=True, text=True)
print(f"HIE atoms: {r.stdout.strip()}")

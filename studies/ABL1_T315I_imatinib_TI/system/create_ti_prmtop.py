#!/usr/bin/env python3
"""
Create combined TI prmtop for T315I mutation using ParmEd tiMerge.

Thermodynamic cycle:
  WT-ABL1:Imatinib --ΔGmut,bound--> T315I-ABL1:Imatinib
  WT-ABL1          --ΔGmut,apo---> T315I-ABL1

This script:
1. Loads wt_complex.prmtop and ti_complex.prmtop
2. Identifies residue 92 (T315) in both
3. Creates combined topology with BOTH protein copies + shared ligand + waters
4. Runs tiMerge to merge common atoms and get softcore masks
5. Creates apo version by stripping imatinib

Outputs:
  ti_merged_bound.prmtop / .inpcrd  — for bound leg TI
  ti_merged_apo.prmtop  / .inpcrd  — for apo leg TI
  ti_masks.txt                      — timask1/2 scmask1/2 for mdin files
"""
import subprocess, sys, os

STUDY = "/home/hn533621/Portfolio/amber-md-agent-improvements/studies/ABL1_T315I_imatinib_TI"
SYS   = f"{STUDY}/system"

WT_PRMTOP  = f"{SYS}/wt_complex.prmtop"
WT_INPCRD  = f"{SYS}/wt_complex.inpcrd"
TI_PRMTOP  = f"{SYS}/ti_complex.prmtop"
TI_INPCRD  = f"{SYS}/ti_complex.inpcrd"

def get_residue_info(prmtop_path):
    """Parse prmtop to find residue 92 (T315) atom range."""
    import parmed
    parm = parmed.load_file(prmtop_path)
    res92 = None
    for i, res in enumerate(parm.residues):
        if i == 91:  # 0-indexed, residue 92 = index 91
            res92 = res
            break
    if res92 is None:
        raise ValueError("Residue 92 not found in prmtop")

    atom_indices = [a.idx + 1 for a in res92.atoms]  # 1-indexed for parmed masks
    backbone = {'N', 'H', 'CA', 'HA', 'C', 'O', 'HA2', 'HA3'}

    sc_atoms = [a for a in res92.atoms if a.name not in backbone]
    sc_indices = [a.idx + 1 for a in sc_atoms]  # 1-indexed

    print(f"  Residue 92: {res92.name}, {len(atom_indices)} atoms")
    print(f"  Side chain atoms: {[a.name for a in sc_atoms]}")
    print(f"  All atom indices (1-indexed): {atom_indices}")
    print(f"  SC atom indices (1-indexed): {sc_indices}")

    return atom_indices, sc_indices, len(parm.atoms)

def main():
    print("Loading WT and T315I prmtops...")

    wt_all_idx, wt_sc_idx, n_wt_atoms = get_residue_info(WT_PRMTOP)
    print(f"WT total atoms: {n_wt_atoms}")

    ti_all_idx, ti_sc_idx, n_ti_atoms = get_residue_info(TI_PRMTOP)
    print(f"T315I total atoms: {n_ti_atoms}")

    # For tiMerge, we need a combined prmtop with BOTH molecules
    # Since parmed can combine structures, we use parmed Python API
    import parmed
    wt  = parmed.load_file(WT_PRMTOP,  WT_INPCRD)
    ti  = parmed.load_file(TI_PRMTOP,  TI_INPCRD)

    # Combined = wt + ti (waters, ligand, protein all doubled)
    # This is necessary for tiMerge; after merge, common atoms are collapsed
    combined = wt + ti
    combined_prmtop = f"{SYS}/ti_combined.prmtop"
    combined_inpcrd = f"{SYS}/ti_combined.inpcrd"
    combined.save(combined_prmtop, overwrite=True)
    combined.save(combined_inpcrd, overwrite=True)
    print(f"\nCombined prmtop: {n_wt_atoms + n_ti_atoms} atoms total")

    # Determine residue masks for tiMerge
    # In combined prmtop:
    #   mol1 = wt residues: :1 to :N_wt_res
    #   mol2 = ti residues: :N_wt_res+1 to :N_total_res
    n_wt_res = len(wt.residues)
    n_ti_res = len(ti.residues)

    # Residue 92 in WT = :92 in combined
    # Residue 92 in TI = :<n_wt_res + 92> in combined
    wt_res92_num  = 92
    ti_res92_num  = n_wt_res + 92

    # Write parmed tiMerge input
    merge_in = f"""\
loadRestrt {combined_inpcrd}
setOverwrite True
tiMerge :{wt_res92_num} :{ti_res92_num} :{wt_res92_num} :{ti_res92_num}
outparm {SYS}/ti_merged_bound.prmtop {SYS}/ti_merged_bound.inpcrd
quit
"""
    # NOTE: broader tiMerge needed — specify entire protein ranges for both molecules
    # This ensures common backbone/water atoms are merged across the full proteins
    merge_in_full = f"""\
loadRestrt {combined_inpcrd}
setOverwrite True
tiMerge :1-{n_wt_res} :{n_wt_res+1}-{n_wt_res+n_ti_res} :{wt_res92_num} :{ti_res92_num}
outparm {SYS}/ti_merged_bound.prmtop {SYS}/ti_merged_bound.inpcrd
quit
"""
    merge_file = f"{SYS}/merge_bound.in"
    with open(merge_file, 'w') as f:
        f.write(merge_in_full)
    print(f"\nRunning tiMerge for bound leg...")
    print(f"mol1: :1-{n_wt_res}, mol2: :{n_wt_res+1}-{n_wt_res+n_ti_res}")
    print(f"scmask1 candidate: :{wt_res92_num}, scmask2 candidate: :{ti_res92_num}")

    result = subprocess.run(
        ['parmed', '-p', combined_prmtop, '-i', merge_file],
        capture_output=True, text=True, cwd=SYS
    )
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    # Parse tiMerge output for masks
    masks = {}
    for line in result.stdout.split('\n'):
        for key in ['timask1', 'timask2', 'scmask1', 'scmask2']:
            if key + "='" in line or key + '=' in line:
                masks[key] = line.strip()

    # Write masks file
    mask_file = f"{SYS}/ti_masks.txt"
    with open(mask_file, 'w') as f:
        f.write("# TI masks from tiMerge output\n")
        f.write("# Copy these into TI mdin files\n\n")
        for k, v in masks.items():
            f.write(f"{v}\n")
    print(f"\nMasks written to {mask_file}")

    # Create apo prmtop by stripping imatinib (STI residue) from merged bound prmtop
    print("\nCreating apo prmtop (stripping imatinib)...")
    apo_in = f"""\
loadRestrt {SYS}/ti_merged_bound.inpcrd
setOverwrite True
strip :STI
outparm {SYS}/ti_merged_apo.prmtop {SYS}/ti_merged_apo.inpcrd
quit
"""
    apo_file = f"{SYS}/make_apo.in"
    with open(apo_file, 'w') as f:
        f.write(apo_in)

    result_apo = subprocess.run(
        ['parmed', '-p', f"{SYS}/ti_merged_bound.prmtop", '-i', apo_file],
        capture_output=True, text=True, cwd=SYS
    )
    print("APO STDOUT:", result_apo.stdout)
    if result_apo.stderr:
        print("APO STDERR:", result_apo.stderr)

    print("\nDone. Files created:")
    for f in ['ti_merged_bound.prmtop', 'ti_merged_bound.inpcrd',
              'ti_merged_apo.prmtop', 'ti_merged_apo.inpcrd', 'ti_masks.txt']:
        path = f"{SYS}/{f}"
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  {f}: {size:,} bytes")
        else:
            print(f"  {f}: MISSING")

if __name__ == '__main__':
    main()

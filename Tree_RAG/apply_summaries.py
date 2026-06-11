#!/usr/bin/env python3
"""
apply_summaries.py — overwrite the high-value DECISION-node summaries (root + 5 parts) in
tree_index.json with summaries reasoned by the agent (Claude Code) from each part's chapter
list. These are the nodes the LLM reads first when picking a branch, so they get authored
summaries instead of the extractive baseline (part divider pages have no prose to extract).

Run AFTER summarize.py. Idempotent.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE / 'tree_index.json'

# node_id -> authored summary (agent-reasoned from the chapter contents)
AUTHORED = {
    "0000": "Top of the Amber 2024 Reference Manual. Five parts: (I) intro & install, "
            "(II) force fields & energy models, (III) system preparation, (IV) running "
            "simulations, (V) analysis.",
    "0001": "Introduction and installation: what the Amber/AmberTools suite is, how data "
            "flows between its programs, and how to build, update and test a distribution "
            "(cmake). Background only — no simulation methods here.",
    "0009": "Amber force fields and energy models: molecular-mechanics force fields for "
            "proteins, nucleic acids, carbohydrates, lipids, ions and water; implicit-solvent "
            "models (Generalized Born GB/SA, GBNSR6, Poisson-Boltzmann PBSA, 3D-RISM); and "
            "quantum methods (sqm semi-empirical, QUICK ab initio, QM/MM). Choose here for "
            "questions about force-field/water-model selection, GB/PB/RISM solvation, or QM.",
    "0070": "System preparation — turning a structure into simulation-ready topology files: "
            "cleaning PDBs (pdb4amber), building systems and adding solvent/ions/bonds in LEaP, "
            "reading/editing prmtop parameters (parmed), ligand parameterization with "
            "antechamber/GAFF, parameter fitting (paramfit, mdgx), metal sites (pyMSMT), RESP "
            "charges (py_resp), and crystal setup. Choose here for tleap, solvateBox, disulfide "
            "bonds, ligand parameters, frcmod/mol2.",
    "0124": "Running simulations — the MD engines and every run-time method: sander and pmemd "
            "(mdin parameters: SHAKE/ntc, PME electrostatics, thermostats/barostats, restraints), "
            "atom-mask selections, enhanced sampling (SGLD, accelerated MD, GaMD, targeted MD, "
            "NEB, string method), free energies (thermodynamic integration, REMD, umbrella "
            "sampling, steered MD), constant-pH and constant-redox MD, NMR/Xray/cryoEM refinement, "
            "and locally-enhanced sampling. Choose here for any mdin keyword or simulation protocol.",
    "0218": "Analysis of trajectories and energies: cpptraj (RMSD/RMSF, hydrogen bonds, "
            "clustering, distances, density — the main analysis engine) and pytraj, end-point "
            "binding free energies (MMPBSA.py, BAR/PBSA, edgembar), free-energy workflows (FEW, "
            "ndfes), SAXS, volumetric maps (MoFT), and mdout/ambpdb utilities. Choose here for "
            "post-processing a finished trajectory.",
}


def main():
    tree = json.loads(TREE.read_text())
    n = 0
    def walk(node):
        nonlocal n
        if node['node_id'] in AUTHORED:
            node['summary'] = AUTHORED[node['node_id']]
            n += 1
        for c in node['nodes']:
            walk(c)
    walk(tree['root'])
    TREE.write_text(json.dumps(tree, indent=2))
    print(f"✓ overwrote {n} decision-node summaries (root + parts) → {TREE.name}")


if __name__ == '__main__':
    main()

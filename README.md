# AmberMD Agent

**A fully autonomous molecular dynamics agent powered by Claude Code.**

Describe what you want to simulate — in plain language — and the agent handles everything else.
It searches six live science databases to gather structures, ligand parameters, and experimental
binding data, reads the Amber manual to plan the correct protocol, writes all input files,
submits jobs to your HPC cluster via SLURM, monitors progress, and interprets the results.
The Amber manual is bundled with the code and indexed for instant lookup — no manual setup required.

Whether it's a standard MD simulation, thermodynamic integration, umbrella sampling, MM-GBSA,
or replica exchange — just describe the system and the question you want to answer.
The agent reads the manual, builds the workflow from scratch, and executes it end to end.

---

## Workflow

![AmberMD Agent Workflow](workflow_figure.png)

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  User: "Calculate binding free energy of erlotinib to EGFR" │
│                                                              │
│  Agent:                                                      │
│    1. Queries live databases via MCP                         │
│       PDB → find best EGFR structure + validate quality      │
│       UniProt → kinase domain boundaries, known mutations    │
│       PubChem → erlotinib SMILES, 3D conformer for params    │
│       ChEMBL → experimental Ki to validate results against   │
│                                                              │
│    2. Queries Amber manual via RAG                           │
│       → "thermodynamic integration setup"                    │
│       → "softcore potentials ifsc"                           │
│       → "lambda schedule recommendations"                    │
│                                                              │
│    3. Plans: "Based on the manual, I'll use TI with..."      │
│       - 11 lambda windows (0.0 → 1.0)                        │
│       - GAFF2 for erlotinib via antechamber                  │
│       - ff14SB + TIP3P                                       │
│       - SLURM array job, one GPU per window                  │
│                                                              │
│    4. Executes using toolkit functions                        │
│       write_mdin() → run_amber() → sbatch → analyze          │
│                                                              │
│    5. Validates: computed ΔG vs ChEMBL experimental Ki       │
└─────────────────────────────────────────────────────────────┘
```

**The AI is the brain. The toolkit is the hands. The manual is the textbook. MCP servers are the library.**

---

## Architecture

```
amber-md-agent/
├── md_agent.py              # Toolkit: PDB ops, file writers, runners, RAG, SLURM
├── CLAUDE.md                # Agent instructions (protocol, rules, known issues)
├── scripts/
│   ├── slurm_template.sh    # One-time cluster config — edit once, used everywhere
│   └── cap_protein.py       # ACE/NME terminal capping utility
├── mcp_servers/             # Live database integrations (6 servers)
│   ├── pdb_server.py        # RCSB PDB: structure search, validation, ligand info
│   ├── uniprot_server.py    # UniProt: protein info, domains, mutations, PTMs
│   ├── pubchem_server.py    # PubChem: compound search, 3D conformers, bioassays
│   ├── alphafold_server.py  # AlphaFold DB: predicted structures, pLDDT confidence
│   └── stringdb_server.py   # STRING-DB: PPI networks, pathway enrichment
├── references/
│   └── (place Amber manual PDF here → gets indexed for RAG)
└── studies/                 # All simulation work lives here
    └── <study_name>/
        ├── raw_pdbs/        # Downloaded PDB files
        ├── system/          # Topology prep (tleap, prmtop, inpcrd)
        ├── simulations/     # min1/ min2/ heat/ equil/ prod/
        ├── analysis/        # cpptraj, .dat files, plots/
        └── logs/            # SLURM outputs, pipeline logs
```

**What's NOT here**: No hardcoded MD pipeline. No fixed umbrella sampling script. No pre-built TI workflow. The agent builds everything on the fly from the manual.

---

## Setup

### 1. Clone and configure your cluster

```bash
git clone https://github.com/yourname/amber-md-agent
cd amber-md-agent
```

Edit `scripts/slurm_template.sh` once for your cluster — paste directly from your cluster's documentation:

```bash
# ── SBATCH Directives ─────────────────────────────────
#SBATCH --partition=gpu          # your partition name
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:a100:1        # your GPU type
#SBATCH --time=168:00:00

# ── Amber Environment Setup ───────────────────────────
module load amber/24             # your amber module name
source /path/to/amber.sh         # if needed for MMPBSA.py
```

Every generated job script will use these settings automatically. Override per-job when needed.

### 2. Index the Amber Manual

> **Already done — `references/amber_index.json` is included in the repo. Skip this step.**

If you ever need to rebuild the index (e.g. after updating the manual PDF):

```bash
# Place your Amber manual PDF in references/
cp ~/Downloads/Amber24_Manual.pdf references/

# Rebuild the RAG index (takes ~1-2 min)
python md_agent.py rag-ingest references/Amber24_Manual.pdf
```

### 3. Activate MCP Database Servers

> **`.mcp.json` is already in the repo** — Claude Code auto-detects it when you open the project.
> All 6 servers will be available immediately with no extra steps.

If you want the servers registered globally (available in all Claude Code sessions), run once
from the project root:

```bash
claude mcp add chembl    -- python3 $(pwd)/mcp_servers/chembl_server.py
claude mcp add pdb       -- python3 $(pwd)/mcp_servers/pdb_server.py
claude mcp add uniprot   -- python3 $(pwd)/mcp_servers/uniprot_server.py
claude mcp add pubchem   -- python3 $(pwd)/mcp_servers/pubchem_server.py
claude mcp add alphafold -- python3 $(pwd)/mcp_servers/alphafold_server.py
claude mcp add stringdb  -- python3 $(pwd)/mcp_servers/stringdb_server.py
```

Verify all 6 servers are connected:
```bash
claude mcp list
# chembl:    ✓ Connected   (EMBL-EBI ChEMBL — bioactivity, Ki/IC50, drug mechanisms)
# pdb:       ✓ Connected   (RCSB PDB — structure search, validation reports)
# uniprot:   ✓ Connected   (UniProt — domains, mutations, PTMs)
# pubchem:   ✓ Connected   (PubChem — SMILES, 3D conformers, bioassays)
# alphafold: ✓ Connected   (AlphaFold DB — predicted structures, pLDDT)
# stringdb:  ✓ Connected   (STRING-DB — PPI networks, pathway enrichment)
```

### 4. Verify

```bash
python md_agent.py check-env
```

---

## Usage — Inside Claude Code

```bash
cd amber-md-agent
claude
```

Then just talk:

```
> Run MD simulation on PDB 1UBQ for 20 ns

> Set up umbrella sampling along the distance between residue 10 CA
  and residue 50 CA, with windows from 5 to 25 Angstrom

> Calculate the binding free energy of erlotinib to EGFR using TI.
  Compare computed ΔG with experimental Ki.

> I want to study the L858R mutation effect on erlotinib binding

> Run replica exchange MD on this small protein at temperatures
  from 300 to 500 K

> Analyze my trajectory — RMSD, RMSF, hydrogen bonds, and PCA

> The equilibration crashed. Look at the mdout and figure out why.
```

### Slash Commands

```
/md-status    Full situational report: running jobs, output checks, next action
/md-jobs      Quick view of running and recently completed SLURM jobs
```

---

## Usage — Direct CLI

```bash
# PDB operations
python md_agent.py fetch 1UBQ
python md_agent.py inspect 1UBQ.pdb
python md_agent.py clean 1UBQ.pdb --output clean.pdb

# Search the Amber manual
python md_agent.py rag-query "how to set up thermodynamic integration"
python md_agent.py rag-query "implicit solvent GB parameters"
python md_agent.py rag-section "Umbrella Sampling"
python md_agent.py rag-pages 256 262

# Write input files
python md_agent.py write-mdin min.mdin --params '{"imin":1,"maxcyc":10000,"ntb":1,"cut":10.0}'
python md_agent.py write-tleap build.in --commands "source leaprc.protein.ff19SB; ..."

# Run Amber programs
python md_agent.py run-amber pmemd.cuda -i prod.mdin -o prod.mdout -p sys.prmtop -c equil.rst7 -r prod.rst7 -x prod.nc
python md_agent.py run-tleap build.in
python md_agent.py run-cpptraj analysis.in

# SLURM — uses slurm_template.sh automatically
python md_agent.py write-slurm run_prod.sh --commands "pmemd.cuda ..." --job-name prod_1UBQ
python md_agent.py sbatch run_prod.sh
python md_agent.py squeue
python md_agent.py sacct

# Read and diagnose outputs
python md_agent.py energy prod.mdout
python md_agent.py convergence rmsd.dat
python md_agent.py read prod.mdout --chars 5000
```

---

## MCP Database Integrations

The agent connects to 6 live science databases via MCP. It uses them proactively — you give a protein name, it finds the structure, ligand SMILES, and experimental data automatically.

| Server | Database | What it provides |
|--------|----------|-----------------|
| ChEMBL | EMBL-EBI ChEMBL | Compound SMILES, IC50/Ki/EC50, drug mechanisms, ADMET |
| PDB | RCSB Protein Data Bank | Structure search, validation reports, ligand info |
| UniProt | UniProt/Swiss-Prot | Protein function, domains, disease mutations, PTMs |
| PubChem | NCBI PubChem | Compound search, 3D conformers, bioassay data |
| AlphaFold | EMBL-EBI AlphaFold DB | Predicted structures, per-residue confidence (pLDDT) |
| STRING-DB | STRING | Protein-protein interaction networks, pathway enrichment |

**Example — full workflow without specifying any IDs:**
```
User: "Study how erlotinib binds EGFR"

Agent uses:
  PDB      → finds best EGFR+erlotinib structure, checks validation report
  UniProt  → kinase domain boundaries, known resistance mutations
  PubChem  → erlotinib SMILES + 3D conformer for antechamber
  ChEMBL   → experimental Ki = 2 nM (validation target for ΔG)
  RAG      → reads TI protocol from Amber manual
  Toolkit  → builds system, parametrizes ligand, runs TI, reports ΔG
```

---

## What Workflows Can It Handle?

Anything in the Amber manual. The agent reads the manual and builds protocols dynamically:

| Workflow | Agent reads manual for... |
|----------|--------------------------|
| Standard MD | Minimization, heating, equilibration params |
| Umbrella Sampling | Restraint definitions, window setup, WHAM |
| Thermodynamic Integration | Lambda windows, softcore params, dvdl integration |
| Replica Exchange (REMD) | Temperature ladder, groupfile, exchange analysis |
| Steered MD | Pulling force, Jarzynski, PMF |
| MM-PBSA / MM-GBSA | MMPBSA.py input, decomposition |
| Constant pH MD | CpHMD setup, titration curves |
| GaMD / aMD | Acceleration params, reweighting |
| Membrane simulations | Lipid21, PACKMOL, membrane builder |
| Implicit solvent (GB) | igb, saltcon, rgbmax params |
| QM/MM | QM region, semiempirical or external QM |
| Free Energy Perturbation | Alchemical setup, BAR/MBAR |
| Metadynamics | Collective variables, hills, convergence |

---

## Design Principles

1. **Manual-first**: The agent queries the Amber manual RAG before planning any protocol — training knowledge alone is not sufficient for accuracy
2. **No hardcoded workflows**: Every protocol is built dynamically from manual + reasoning
3. **Database-first for targets**: When given a protein or compound name, look it up rather than asking the user for IDs
4. **Inspect before acting**: Always analyze the PDB before preparing the system
5. **Diagnose and adapt**: If a step fails, read the output, query the manual, fix, retry
6. **Transparent**: The agent explains what it found in the manual and why it chose specific parameters
7. **User in the loop**: Ambiguous decisions are escalated to the user

---

*Built for computational biologists who want an AI that thinks like a scientist, not a script runner.*

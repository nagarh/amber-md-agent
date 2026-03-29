#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# AmberMD Agent — SLURM Cluster Configuration Template
#
# Configure this file ONCE for your cluster.
# md_agent.py reads it automatically when generating every SLURM job script.
#
# Instructions:
#   1. Replace the #SBATCH lines with whatever your cluster requires.
#      Paste directly from your cluster's documentation or an existing script.
#      You can add any directives: --account, --qos, --constraint, --mail-user, etc.
#   2. Set the environment lines (module load / source) to match your cluster.
#   3. Optionally set WORK_BASE to your scratch/data directory.
#
# You never need to edit generated job scripts — change it here instead.
# ─────────────────────────────────────────────────────────────────────────────

# ── SBATCH Directives ─────────────────────────────────────────────────────────
# These lines are copied verbatim into every generated job script.
# --job-name, --output, --error, and --array (for array jobs) are added
# automatically — do not include them here.
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --time=168:00:00

# ── Amber Environment Setup ───────────────────────────────────────────────────
# These lines are copied verbatim after the SBATCH block in every job script.
# Add module loads, source commands, conda activations, or any setup needed.
module load amber/24
source /opt/shared/apps/amber/24/amber.sh

# ── Work Base Directory ───────────────────────────────────────────────────────
# Base directory where simulation output will be written.
# Studies go under: WORK_BASE/studies/<study_name>/
# Leave empty to use the current directory.
WORK_BASE="/home/hn533621/Portfolio/amber-md-agent"

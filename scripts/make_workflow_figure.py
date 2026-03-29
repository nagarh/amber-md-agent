#!/usr/bin/env python3
"""
AmberMD Agent — clean single-slide workflow figure.
Design: horizontal pipeline, big icons, minimal text.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe

fig, ax = plt.subplots(figsize=(20, 11.25))
ax.set_xlim(0, 20)
ax.set_ylim(0, 11.25)
ax.axis("off")

BG = "#0F1419"
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

WHITE  = "#E8EAED"
DIM    = "#6B7280"
ACCENT = "#FFA657"

COLS = ["#58A6FF", "#BC8CFF", "#F78166", "#3FB950", "#E3B341", "#79C0FF"]

shadow = [pe.withStroke(linewidth=3, foreground=BG)]

def txt(x, y, s, sz=11, c=WHITE, w="normal", ha="center", va="center"):
    ax.text(x, y, s, fontsize=sz, color=c, weight=w, ha=ha, va=va,
            zorder=6, linespacing=1.45, path_effects=shadow)

def rbox(x, y, w, h, col, af=0.14, lw=2.2, r=0.35):
    ax.add_patch(mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
        facecolor=col, alpha=af, lw=0, zorder=2))
    ax.add_patch(mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
        facecolor="none", edgecolor=col, alpha=0.6, lw=lw, zorder=3))

# ═══════════════════════════════════════════════════════════════════════════
#  TITLE
# ═══════════════════════════════════════════════════════════════════════════
txt(10, 10.55, "AmberMD Agent", sz=30, c=WHITE, w="bold")
txt(10, 9.95, "AI-Driven Molecular Dynamics  \u2014  From Target to \u0394G in One Prompt",
    sz=14, c=DIM)

# ═══════════════════════════════════════════════════════════════════════════
#  MAIN PIPELINE — 6 stages, generous spacing
# ═══════════════════════════════════════════════════════════════════════════
BW = 2.55   # box width
BH = 5.8    # box height
BY = 3.0    # box y
GAP = 0.32
XS = 0.45

stages = [
    ("Input",          COLS[0], "Protein + Ligand\nname",      "Natural language\nno IDs needed"),
    ("Databases",      COLS[1], "6 MCP Servers",               "PDB \u00b7 UniProt\nPubChem \u00b7 ChEMBL\nAlphaFold \u00b7 STRING"),
    ("Amber\nManual",  COLS[2], "RAG Search",                  "Protocol & params\nfrom the source\nbefore every step"),
    ("Prepare",        COLS[3], "antechamber\ntLEaP",          "Force field\nassignment\ntopology + solvation"),
    ("Simulate",       COLS[4], "pmemd.cuda\nSLURM GPU",       "Min \u2192 Heat \u2192 Equil\n\u2192 Production\n+ Advanced Sampling"),
    ("Analyze",        COLS[5], "cpptraj\nMM-PBSA / WHAM",     "\u0394G computed\nvs experimental Ki\nfrom ChEMBL"),
]

for i, (title, col, mid, bot) in enumerate(stages):
    x = XS + i * (BW + GAP)
    cx = x + BW / 2

    # Main box
    rbox(x, BY, BW, BH, col, af=0.10, lw=2.5)

    # Step number badge
    ax.add_patch(plt.Circle((cx, BY + BH - 0.6), 0.38,
                             color=col, alpha=0.85, zorder=5))
    txt(cx, BY + BH - 0.6, str(i + 1), sz=18, c="#0F1419", w="bold")

    # Title
    txt(cx, BY + BH - 1.5, title, sz=15, c=col, w="bold")

    # Divider line
    ax.plot([x + 0.25, x + BW - 0.25],
            [BY + BH - 2.15, BY + BH - 2.15],
            color=col, lw=1.2, alpha=0.35, zorder=3)

    # Middle description
    txt(cx, BY + BH - 2.85, mid, sz=12, c=WHITE)

    # Lower divider
    ax.plot([x + 0.25, x + BW - 0.25],
            [BY + BH - 3.55, BY + BH - 3.55],
            color=col, lw=1.0, alpha=0.25, zorder=3)

    # Bottom detail
    txt(cx, BY + 1.1, bot, sz=10.5, c=ACCENT)

    # Arrow to next stage
    if i < len(stages) - 1:
        ax.annotate("", xy=(x + BW + GAP - 0.05, BY + BH / 2),
                    xytext=(x + BW + 0.05, BY + BH / 2),
                    arrowprops=dict(arrowstyle="-|>", color=col,
                                    lw=3.5, mutation_scale=22), zorder=5)

# ═══════════════════════════════════════════════════════════════════════════
#  BOTTOM TAGLINE
# ═══════════════════════════════════════════════════════════════════════════
txt(10, 2.2,
    "The AI is the brain.    The toolkit is the hands.    The manual is the textbook.",
    sz=12, c=DIM)

txt(10, 1.5, "Claude Code  \u00b7  Amber24  \u00b7  SLURM HPC  \u00b7  6 Live Database APIs",
    sz=10, c="#3D4452")

# subtle glow
ax.scatter([10], [10.55], s=20000, color=ACCENT, alpha=0.025, zorder=1)

# ── Save ──────────────────────────────────────────────────────────────────
out = "workflow_figure.png"
plt.tight_layout(pad=0.3)
plt.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG)
print(f"Saved: {out}")
plt.close()

#!/bin/bash
# ──────────────────────────────────────────────────────────────
# AmberMD Agent — Setup Script
# ──────────────────────────────────────────────────────────────

set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║  AmberMD Agent — Setup                              ║"
echo "╚══════════════════════════════════════════════════════╝"

# 1. Check Python
echo -e "\n[1/5] Checking Python..."
python3 --version || { echo "❌ Python 3 not found"; exit 1; }

# 2. Install Python dependencies
echo -e "\n[2/5] Installing Python dependencies..."
pip install -r requirements.txt --quiet 2>/dev/null || \
pip3 install -r requirements.txt --quiet 2>/dev/null || \
echo "⚠ pip install failed — install numpy and matplotlib manually"

# 3. Check AmberTools
echo -e "\n[3/5] Checking AmberTools installation..."
TOOLS=("tleap" "sander" "cpptraj" "antechamber" "pdb4amber" "parmchk2")
ALL_FOUND=true
for tool in "${TOOLS[@]}"; do
    if command -v "$tool" &>/dev/null; then
        echo "  ✓ $tool"
    else
        echo "  ✗ $tool — NOT FOUND"
        ALL_FOUND=false
    fi
done

if [ "$ALL_FOUND" = false ]; then
    echo ""
    echo "⚠ Some AmberTools not found. Install AmberTools:"
    echo "  conda install -c conda-forge ambertools=24"
    echo "  — or —"
    echo "  Download from https://ambermd.org/GetAmber.php"
fi

# 4. Check GPU (optional)
echo -e "\n[4/5] Checking GPU..."
if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || true
    if command -v pmemd.cuda &>/dev/null; then
        echo "  ✓ pmemd.cuda available — GPU acceleration enabled"
    else
        echo "  ⚠ GPU found but pmemd.cuda not installed"
    fi
else
    echo "  ℹ No GPU detected — will use CPU (sander)"
fi

# 5. Check for Amber manual
echo -e "\n[5/5] Checking for Amber manual..."
if [ -f "references/amber_manual.txt" ] || [ -f "references/amber_manual.pdf" ]; then
    echo "  ✓ Manual found in references/"
    if [ -f "references/amber_index.json" ]; then
        echo "  ✓ Manual index exists"
    else
        echo "  ℹ Run: python scripts/rag_amber.py ingest --input references/amber_manual.pdf"
    fi
else
    echo "  ℹ No manual found. Place Amber manual in references/ for RAG support."
    echo "    Supported formats: .pdf, .txt"
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Setup complete! Run simulations with:              ║"
echo "║                                                      ║"
echo "║  python md_agent.py run --pdb 1UBQ --time 10        ║"
echo "║                                                      ║"
echo "║  Or inside Claude Code:                              ║"
echo "║  claude \"Run MD simulation on PDB 1UBQ for 10ns\"    ║"
echo "╚══════════════════════════════════════════════════════╝"

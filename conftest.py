import sys
from pathlib import Path

root = Path(__file__).parent
sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp_servers"))

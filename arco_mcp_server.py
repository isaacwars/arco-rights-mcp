"""Local launcher for the ARCO MCP server without installing the package."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from arco_mcp.server import main


if __name__ == "__main__":
    main()


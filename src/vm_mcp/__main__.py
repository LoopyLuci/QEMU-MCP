"""Entry point for python -m vm_mcp."""
from __future__ import annotations

import asyncio
import sys

# Ensure src is on the path when run as module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vm_mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())

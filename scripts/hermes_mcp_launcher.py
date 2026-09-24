#!/usr/bin/env python3
"""Hermes MCP launcher for vm-mcp.

Changes to the vm-mcp project directory so pydantic-settings can find .env,
then runs the MCP server via stdio.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(r"C:\Projects\VM-Harness").resolve()
if not PROJECT_DIR.is_dir():
    print(f"ERROR: project dir not found: {PROJECT_DIR}", file=sys.stderr)
    sys.exit(1)

os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR / "src"))

env_path = PROJECT_DIR / ".env"
if not env_path.is_file():
    print(f"ERROR: .env not found at {env_path}", file=sys.stderr)
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv(str(env_path))

from vm_mcp.__main__ import main

asyncio.run(main())

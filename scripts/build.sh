#!/usr/bin/env bash
# Build the vm-mcp package in development mode.
# Run from the project root (where pyproject.toml lives).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Installing dependencies..."
pip install -e ".[dev]"

echo "==> Running tests..."
python -m pytest tests/ -v

echo "==> Done."

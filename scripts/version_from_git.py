# VM-Harness version detection — reads git tag if available, falls back to pyproject.toml

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    import tomli as tomllib  # Python < 3.11
except ImportError:
    import tomllib  # Python 3.11+


def get_version(project_root: Path | None = None) -> str:
    """Return the version string for the current build.

    Priority:
    1. Git tag (e.g. "v1.2.3" → "1.2.3") if we're inside a git repo with tags.
    2. pyproject.toml [project] version field.
    3. "0.0.0" as a last resort.
    """
    root = project_root or Path(__file__).resolve().parent.parent

    # 1. Try git describe --tags --abbrev=0
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(root),
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode().strip()
        # Strip leading 'v' or 'V' if present
        if tag.lower().startswith("v"):
            tag = tag[1:]
        # Validate it looks like a semver
        parts = tag.split(".")
        if len(parts) >= 2 and all(p.isdigit() for p in parts[:2]):
            return tag
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    # 2. Read from pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        data = tomllib.loads(pyproject.read_text())
        version = data.get("project", {}).get("version", "")
        if version:
            return version

    # 3. Fallback
    return "0.0.0"


if __name__ == "__main__":
    v = get_version()
    print(v)

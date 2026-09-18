"""Generate .env from .env.example for first-time setup."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def generate_env(env_path: str = ".env", example_path: str = ".env.example") -> bool:
    """Copy .env.example to .env if .env does not exist."""
    env = Path(env_path)
    example = Path(example_path)

    if env.exists():
        print(f".env already exists at {env.resolve()}")
        return False

    if not example.exists():
        print(f"Error: {example.resolve()} not found")
        return False

    shutil.copy2(example, env)
    print(f"Created {env.resolve()} from {example.resolve()}")
    print("Please edit .env to set your values (especially SSH_PASSWORD).")
    return True


if __name__ == "__main__":
    generate_env()

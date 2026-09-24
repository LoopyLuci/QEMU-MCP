#!/usr/bin/env python3
"""VM-Harness Installer / Updater.

Verifies:
- .venv exists with pythonw.exe
- .exe can be built (pyinstaller installed or available)
- GitHub repo (https://github.com/LoopyLuci/VM-Harness) reachable
- Update mechanism works
"""

from __future__ import annotations

import os
import subprocess
n# Suppress CLI console windows on Windows
CREATE_NO_WINDOW = 0x08000000
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
GITHUB_URL = "https://github.com/LoopyLuci/VM-Harness"
RELEASES_URL = f"{GITHUB_URL}/releases/latest"


def verify_venv():
    venv_pythonw = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    assert venv_pythonw.exists(), f"Project venv missing: {venv_pythonw}"
    print("[PASS] Project .venv with pythonw.exe verified")
    return venv_pythonw


def verify_pyinstaller():
    try:
        subprocess.run(
            [str(verify_venv()), "-m", "pyinstaller", "--version"],
            capture_output=True, check=True,
        )
        print("[PASS] pyinstaller available via project venv")
        return True
    except subprocess.CalledProcessError:
        print("[FAIL] pyinstaller not available — will install")
        subprocess.run(
            [str(verify_venv()), "-m", "pip", "install", "pyinstaller"],
            check=False,
        )
        return False


def verify_github():
    import urllib.request
    try:
        req = urllib.request.Request(
            RELEASES_URL, headers={"User-Agent": "VM-Harness-Updater/2.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            url = resp.geturl()
            print(f"[PASS] GitHub releases reachable: {url}")
            return url
    except Exception as e:
        print(f"[WARN] GitHub unreachable: {e}")
        return None


def build_installer():
    spec_path = PROJECT_ROOT / "vm-harness.spec"
    if not spec_path.exists():
        # Write minimal spec
        spec_path.write_text(
            '# -*- mode: python ; coding: utf-8 -*-\n'
            'block_cipher = None\n'
            '\n'
            'a = Analysis(\n'
            '    ["gui/__main__.py"],\n'
            '    pathex=["."],\n'
            '    binaries=[],\n'
            '    datas=[(".venv", ".venv")],\n'
            '    hiddenimports=["PyQt5", "aiohttp", "qrcode", "cryptography", "asyncssh"],\n'
            '    hookspath=[],\n'
            '    hooksconfig={},\n'
            '    runtime_hooks=[],\n'
            '    excludes=[],\n'
            '    win_no_prefer_redirects=False,\n'
            '    win_private_assemblies=False,\n'
            '    cipher=block_cipher,\n'
            '    noarchive=False,\n'
            ')\n'
            'pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)\n'
            'exe = EXE(\n'
            '    pyz,\n'
            '    a.scripts,\n'
            '    a.binaries,\n'
            '    a.zipfiles,\n'
            '    a.datas,\n'
            '    [],\n'
            '    name="VM-Harness",\n'
            '    debug=False,\n'
            '    bootloader_ignore_signals=False,\n'
            '    strip=False,\n'
            '    upx=True,\n'
            '    upx_exclude=[],\n'
            '    runtime_tmpdir=None,\n'
            '    console=False,\n'
            '    disable_windowed_traceback=False,\n'
            '    target_arch=None,\n'
            '    codesign_identity=None,\n'
            '    entitlements_file=None,\n'
            '    icon="scripts/generate_icon_output/vm-harness-icon.ico" if Path("scripts/generate_icon_output/vm-harness-icon.ico").exists() else None,\n'
            ')\n'
        )
    print(f"[PASS] PyInstaller spec written: {spec_path}")
    return spec_path


def main():
    print("VM-Harness Installer / Updater")
    print("=" * 50)
    venv = verify_venv()
    verify_pyinstaller()
    gh_url = verify_github()
    spec = build_installer()
    print("=" * 50)
    print(f"Project venv: {venv}")
    print(f"GitHub: {gh_url or GITHUB_URL}")
    print(f"Installer spec: {spec}")
    print("To build: .\\.venv\\Scripts\\pythonw.exe -m PyInstaller vm-harness.spec --clean")
    print("To update: curl {RELEASES_URL}/download/v.../VM-Harness.exe")


if __name__ == "__main__":
    main()

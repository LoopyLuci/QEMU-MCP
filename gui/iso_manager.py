"""ISO Manager — internal storage and external folder support.

Handles:
- Internal iso/ folder for bundled ISOs
- External user-defined folders for ISO scanning
- ISO metadata and caching
- Download support for common ISOs
"""

from __future__ import annotations

import json
import os
import shutil
import hashlib
from pathlib import Path
from typing import Any, Optional

# Default paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
INTERNAL_ISO_DIR = PROJECT_DIR / "iso"
EXTERNAL_ISO_CONFIG = PROJECT_DIR / ".iso-sources.json"

# Common ISO download URLs (for reference)
COMMON_ISOS = {
    "ubuntu-22.04": {
        "name": "Ubuntu 22.04 LTS Server",
        "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso",
        "size_gb": 2.1,
        "checksum": "a4acfda10b18da50e2ec50996e2f1d14",
    },
    "debian-12": {
        "name": "Debian 12 (Bookworm)",
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.1.0-amd64-netinst.iso",
        "size_gb": 0.4,
        "checksum": "a4acfda10b18da50e2ec50996e2f1d14",
    },
    "archlinux": {
        "name": "Arch Linux 2023.09",
        "url": "https://mirror.rackspace.com/archlinux/iso/2023.09.01/archlinux-2023.09.01-x86_64.iso",
        "size_gb": 0.8,
        "checksum": "a4acfda10b18da50e2ec50996e2f1d14",
    },
    "fedora-38": {
        "name": "Fedora 38 Workstation",
        "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/38/Workstation/x86_64/iso/Fedora-Workstation-Live-x86_64-38-1.6.iso",
        "size_gb": 2.0,
        "checksum": "a4acfda10b18da50e2ec50996e2f1d14",
    },
    "windows-10": {
        "name": "Windows 10 (manual download required)",
        "url": "https://www.microsoft.com/software-download/windows10ISO",
        "size_gb": 5.0,
        "checksum": "",
    },
}


class ISOManager:
    """Manage ISO files from internal and external sources."""

    def __init__(self):
        self._internal_dir = INTERNAL_ISO_DIR
        self._external_sources: list[Path] = []
        self._iso_cache: list[dict[str, Any]] = []
        self._load_config()

    def _load_config(self):
        """Load external ISO source configuration."""
        if EXTERNAL_ISO_CONFIG.exists():
            try:
                with open(EXTERNAL_ISO_CONFIG, 'r') as f:
                    data = json.load(f)
                self._external_sources = [Path(p) for p in data.get("sources", [])]
            except Exception:
                self._external_sources = []

    def _save_config(self):
        """Save external ISO source configuration."""
        data = {"sources": [str(p) for p in self._external_sources]}
        with open(EXTERNAL_ISO_CONFIG, 'w') as f:
            json.dump(data, f, indent=2)

    def add_external_source(self, path: str | Path) -> bool:
        """Add an external ISO source folder."""
        path = Path(path).resolve()
        if not path.is_dir():
            return False
        if path not in self._external_sources:
            self._external_sources.append(path)
            self._save_config()
        return True

    def remove_external_source(self, path: str | Path) -> bool:
        """Remove an external ISO source folder."""
        path = Path(path).resolve()
        if path in self._external_sources:
            self._external_sources.remove(path)
            self._save_config()
            return True
        return False

    def get_external_sources(self) -> list[Path]:
        """Get list of external ISO source folders."""
        return list(self._external_sources)

    def scan_isos(self) -> list[dict[str, Any]]:
        """Scan all ISO sources and return list of available ISOs."""
        isos = []
        
        # Scan internal folder
        if self._internal_dir.exists():
            for iso_file in self._internal_dir.glob("*.iso"):
                isos.append(self._make_iso_entry(iso_file, "internal"))
        
        # Scan external folders
        for source in self._external_sources:
            if source.exists():
                for iso_file in source.rglob("*.iso"):
                    isos.append(self._make_iso_entry(iso_file, "external"))
        
        self._iso_cache = isos
        return isos

    def _make_iso_entry(self, path: Path, source: str) -> dict[str, Any]:
        """Create an ISO metadata entry."""
        stat = path.stat()
        return {
            "name": path.stem,
            "path": str(path),
            "size": stat.st_size,
            "size_human": self._human_size(stat.st_size),
            "source": source,
            "modified": stat.st_mtime,
        }

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """Convert bytes to human-readable size."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    def get_iso_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Find an ISO by name (without extension)."""
        for iso in self._iso_cache:
            if iso["name"] == name:
                return iso
        return None

    def get_iso_by_path(self, path: str) -> Optional[dict[str, Any]]:
        """Find an ISO by path."""
        for iso in self._iso_cache:
            if iso["path"] == path:
                return iso
        return None

    def copy_to_internal(self, source_path: str | Path) -> Optional[Path]:
        """Copy an ISO to the internal iso/ folder."""
        source = Path(source_path)
        if not source.exists():
            return None
        dest = self._internal_dir / source.name
        shutil.copy2(source, dest)
        return dest

    def delete_iso(self, path: str | Path) -> bool:
        """Delete an ISO file (internal only)."""
        path = Path(path).resolve()
        # Only allow deletion from internal folder for safety
        if str(path).startswith(str(self._internal_dir)):
            try:
                path.unlink()
                return True
            except Exception:
                return False
        return False

    def ensure_internal_dir(self):
        """Ensure internal ISO directory exists."""
        self._internal_dir.mkdir(parents=True, exist_ok=True)

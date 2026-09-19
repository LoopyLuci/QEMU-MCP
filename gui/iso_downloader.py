"""ISO Download Manager — download ISOs with progress tracking."""

from __future__ import annotations

import hashlib
import logging
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from gui.iso_manager import INTERNAL_ISOS

logger = logging.getLogger("qemu-mcp.download")


class ISODownloader:
    """Download ISO files with progress tracking and verification."""

    def __init__(self, dest_dir: Optional[Path] = None):
        self._dest_dir = dest_dir or INTERNAL_ISOS

    def download(
        self,
        url: str,
        filename: str | None = None,
        expected_checksum: str | None = None,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> Path:
        """Download an ISO file with progress tracking.

        Args:
            url: URL to download from
            filename: Optional filename (defaults to URL basename)
            expected_checksum: Optional MD5 checksum for verification
            progress_callback: Optional callback(bytes_downloaded, total_size, speed)

        Returns:
            Path to downloaded file

        Raises:
            Exception: On download failure or checksum mismatch
        """
        if not filename:
            filename = url.split("/")[-1]

        dest = self._dest_dir / filename

        def report_progress(block_num, block_size, total_size):
            if progress_callback:
                downloaded = block_num * block_size
                speed = block_size  # bytes per block
                progress_callback(downloaded, total_size, speed)

        logger.info("Downloading %s to %s", url, dest)
        urllib.request.urlretrieve(url, dest, reporthook=report_progress)

        if expected_checksum:
            actual = self._md5(dest)
            if actual != expected_checksum:
                dest.unlink()
                raise Exception(f"Checksum mismatch: expected {expected_checksum}, got {actual}")

        logger.info("Download complete: %s", dest)
        return dest

    @staticmethod
    def _md5(path: Path) -> str:
        """Calculate MD5 hash of a file."""
        md5 = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    @staticmethod
    def verify_checksum(path: Path, expected: str) -> bool:
        """Verify a file's checksum."""
        return ISODownloader._md5(path) == expected

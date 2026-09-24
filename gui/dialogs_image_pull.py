"""Image Pull Progress Dialog — pull a Docker image with live progress display.

Provides a QProgressDialog that parses Docker's streamed pull output
(JSON per-layer progress) and shows a real-time progress bar with the
current layer status.  Runs the blocking docker-py call in a QThread
to keep the GUI responsive.

Usage:
    from gui.dialogs_image_pull import ImagePullDialog
    dlg = ImagePullDialog("ubuntu:22.04", parent=self)
    dlg.exec_()
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QMessageBox,
    QProgressDialog,
)

from gui.theme import T


# ═══════════════════════════════════════════════════════════════════════════════
# Worker Thread — runs the blocking docker pull in the background
# ═══════════════════════════════════════════════════════════════════════════════

class _PullWorker(QThread):
    """Background worker that pulls a Docker image and emits progress signals."""

    # (status_text, layer_id, pct, detail_str)
    progress = pyqtSignal(str, str, int, str)
    # (success: bool, message: str)
    finished = pyqtSignal(bool, str)

    def __init__(self, image_name: str, parent=None):
        super().__init__(parent)
        self._image_name = image_name
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation (checked between stream chunks)."""
        self._cancelled = True

    def run(self) -> None:
        """Execute docker.images.pull() with streaming and emit progress."""
        try:
            from docker import DockerClient
            from docker.errors import DockerException, ImageNotFound, APIError
        except ImportError:
            self.finished.emit(False, "docker-py not installed")
            return

        client: Optional[DockerClient] = None
        try:
            client = DockerClient()
        except Exception as e:
            self.finished.emit(False, f"Cannot connect to Docker: {e}")
            return

        try:
            # Use the low-level API — client.images.pull() no longer supports
            # stream=True in docker-py 7.x.  client.api.pull() returns a
            # generator of JSON dicts (one per event).
            stream = client.api.pull(self._image_name, stream=True, decode=True)

            last_pct = 0

            for chunk in stream:
                if self._cancelled:
                    self.finished.emit(False, "Pull cancelled by user")
                    return

                if not isinstance(chunk, dict):
                    continue

                status: str = chunk.get("status", "")
                layer_id: str = chunk.get("id", "")
                progress_detail: Dict[str, Any] = chunk.get("progressDetail", {})

                # Compute percentage from progressDetail
                pct = last_pct
                if progress_detail and "total" in progress_detail and "current" in progress_detail:
                    total = progress_detail["total"]
                    current = progress_detail["current"]
                    if total > 0:
                        pct = min(int(current * 100 / total), 100)
                        last_pct = pct

                # Build a human-readable detail string
                detail_str = ""
                if progress_detail and "current" in progress_detail and "total" in progress_detail:
                    detail_str = (
                        self._format_bytes(progress_detail["current"])
                        + " / "
                        + self._format_bytes(progress_detail["total"])
                    )

                self.progress.emit(status, layer_id, pct, detail_str)

            self.finished.emit(
                True, f"Image '{self._image_name}' pulled successfully"
            )

        except ImageNotFound:
            self.finished.emit(False, f"Image '{self._image_name}' not found in registry")
        except APIError as e:
            if "unauthorized" in str(e).lower() or "authentication" in str(e).lower():
                self.finished.emit(False, f"Authentication failed: {e}")
            else:
                self.finished.emit(False, f"Docker API error: {e}")
        except DockerException as e:
            self.finished.emit(False, f"Docker error: {e}")
        except Exception as e:
            self.finished.emit(False, f"Unexpected error: {e}")
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    @staticmethod
    def _format_bytes(n: int) -> str:
        """Format a byte count as a human-readable string."""
        if n < 1024:
            return f"{n}B"
        elif n < 1024 * 1024:
            return f"{n / 1024:.1f}KB"
        elif n < 1024 * 1024 * 1024:
            return f"{n / (1024 * 1024):.1f}MB"
        else:
            return f"{n / (1024 * 1024 * 1024):.1f}GB"


# ═══════════════════════════════════════════════════════════════════════════════
# Progress Dialog
# ═══════════════════════════════════════════════════════════════════════════════

class ImagePullDialog(QProgressDialog):
    """QProgressDialog that pulls a Docker image with live progress display.

    Shows a progress bar, the current layer being pulled, transfer size
    information, and a cancel button.  On completion shows a modal message
    indicating success or failure.

    The blocking docker-py call runs in a background QThread; streamed
    progress updates are delivered via Qt signals to keep the GUI responsive.
    """

    def __init__(self, image_name: str, parent=None):
        # Buffer label text with newlines so it doesn't resize the dialog
        super().__init__(f"Pulling '{image_name}'…", "Cancel", 0, 100, parent)
        self._image_name = image_name
        self._worker: Optional[_PullWorker] = None

        self.setWindowTitle(f"Pulling Image — {image_name}")
        self.setMinimumWidth(520)
        self.setWindowModality(Qt.ApplicationModal)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setValue(0)
        self.setStyleSheet(self._build_stylesheet())

        # Track the last layer id to avoid redundant label updates
        self._last_layer: str = ""

        self.canceled.connect(self._on_cancel)

    def start_pull(self) -> None:
        """Start the background pull thread."""
        self._worker = _PullWorker(self._image_name, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def exec_(self) -> int:  # noqa: N802 — Qt naming convention
        """Start the pull and show the dialog modally."""
        self.start_pull()
        return super().exec_()

    # ── Signal Handlers ─────────────────────────────────────────────────────

    def _on_progress(self, status: str, layer_id: str, pct: int, detail: str):
        """Update the progress bar and labels from the worker thread."""
        self.setValue(pct)

        if status:
            label = f"Pulling '{self._image_name}': {status}"
            if layer_id:
                label += f" [{layer_id}]"
            self.setLabelText(label)

        if detail:
            # Append transfer info on a second line via rich-text label
            current_text = self.labelText() or ""
            # We only update detail if it's a new layer or pct change
            if layer_id != self._last_layer:
                self._last_layer = layer_id

        # Keep the GUI responsive during heavy streaming
        QApplication.processEvents()

    def _on_finished(self, success: bool, message: str):
        """Handle completion — close progress dialog and show result."""
        if success:
            self.setValue(100)
        self.close()

        if success:
            QMessageBox.information(self, "Image Pull Complete", message)
        else:
            QMessageBox.critical(self, "Image Pull Failed", message)

    def _on_cancel(self):
        """Forward cancel to the worker thread."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.setLabelText("Cancelling…")

    # ── Styling ─────────────────────────────────────────────────────────────

    def _build_stylesheet(self) -> str:
        """Build QSS for the progress dialog matching the app theme."""
        return (
            f"QProgressDialog {{ background: {T.BG_PRIMARY}; }}"
            f"QLabel {{ color: {T.TEXT_PRIMARY}; font-size: {T.FS_MD}px; }}"
            f"QProgressBar {{"
            f"  background: {T.BG_SECONDARY};"
            f"  border: 1px solid {T.BG_TERTIARY};"
            f"  border-radius: {T.R_SM}px;"
            f"  height: 20px;"
            f"  text-align: center;"
            f"  color: {T.TEXT_PRIMARY};"
            f"  font-size: {T.FS_SM}px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background: {T.BRAND};"
            f"  border-radius: {T.R_SM}px;"
            f"}}"
            f"QPushButton {{"
            f"  background: {T.BG_SECONDARY};"
            f"  color: {T.TEXT_PRIMARY};"
            f"  border: 1px solid {T.BG_TERTIARY};"
            f"  border-radius: {T.R_SM}px;"
            f"  padding: 6px 16px;"
            f"  font-size: {T.FS_MD}px;"
            f"  min-width: 80px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {T.ERROR_BG};"
            f"  border-color: {T.ERROR};"
            f"}}"
        )

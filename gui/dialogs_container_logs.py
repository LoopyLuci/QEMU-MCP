"""Container Logs Dialog — fetch and display container logs via REST API.

Provides a QDialog with auto-refresh, tail-line selector, and monospace
QTextBrowser for viewing Docker/Podman container logs.

Usage:
    from gui.dialogs_container_logs import ContainerLogsDialog
    dlg = ContainerLogsDialog(container_name="my-container", parent=self)
    dlg.exec_()
"""

from __future__ import annotations

from typing import Any

import json
import ssl
import urllib.request
import urllib.error

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextBrowser,
    QComboBox, QLabel, QMessageBox, QSizePolicy, QApplication, QFrame,
)

from gui.theme import T
from gui.widgets import Card, StatusIndicator


class ContainerLogsDialog(QDialog):
    """Dialog for viewing container logs with auto-refresh and tail control.

    Fetches logs from the REST endpoint:
        GET /api/v1/containers/{name}/logs
    Expects JSON response: {"logs": "..."}
    """

    DEFAULT_BASE_URL = "https://127.0.0.1:8443/api/v1/containers"
    AUTO_REFRESH_MS = 5000  # 5 seconds

    def __init__(self, container_name: str, base_url: str = "",
                 parent=None):
        super().__init__(parent)
        self._container_name = container_name
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._auto_refresh_enabled = False

        self.setWindowTitle(f"Logs — {container_name}")
        self.setMinimumSize(720, 480)
        self.resize(800, 560)
        self.setStyleSheet(
            f"QDialog {{ background: {T.BG_PRIMARY}; }}"
            f"QLabel {{ color: {T.TEXT_PRIMARY}; font-size: {T.FS_MD}px; }}"
        )

        self._build_ui()
        self._fetch_logs()

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self):
        """Build the dialog layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(T.LG, T.LG, T.LG, T.LG)
        main_layout.setSpacing(T.MD)

        # Header with container name and status
        header = QWidget(self)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(f"Container: {self._container_name}")
        title_label.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: {T.FS_XL}px; font-weight: bold;"
        )
        hl.addWidget(title_label)
        hl.addStretch()

        self._status_indicator = StatusIndicator(QColor("#ef4444"))
        hl.addWidget(self._status_indicator)
        self._status_label = QLabel("Disconnected")
        self._status_label.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FS_SM}px;"
        )
        hl.addWidget(self._status_label)

        main_layout.addWidget(header)

        # Toolbar: refresh, tail selector, auto-refresh toggle
        toolbar = QWidget(self)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(T.SM)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setStyleSheet(
            f"background: {T.BRAND}; color: {T.TEXT_PRIMARY}; border: none;"
            "border-radius: 6px; padding: 6px 16px; font-weight: bold;"
        )
        self._refresh_btn.clicked.connect(self._fetch_logs)
        tb_layout.addWidget(self._refresh_btn)

        tb_layout.addSpacing(T.MD)

        tail_label = QLabel("Tail:")
        tail_label.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: {T.FS_MD}px;"
        )
        tb_layout.addWidget(tail_label)

        self._tail_combo = QComboBox()
        self._tail_combo.addItems(["50", "100", "200"])
        self._tail_combo.setCurrentText("100")
        self._tail_combo.setStyleSheet(
            f"QComboBox {{ background: {T.BG_SECONDARY}; color: {T.TEXT_PRIMARY};"
            f" border: 1px solid {T.BG_TERTIARY}; border-radius: {T.R_SM}px;"
            " padding: 4px 8px; font-size: 12px; min-width: 60px; }}"
            f"QComboBox:hover {{ border-color: {T.BRAND}; }}"
        )
        self._tail_combo.currentTextChanged.connect(self._fetch_logs)
        tb_layout.addWidget(self._tail_combo)

        tb_layout.addStretch()

        self._auto_refresh_btn = QPushButton("Auto-refresh: OFF")
        self._auto_refresh_btn.setCheckable(True)
        self._auto_refresh_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG_TERTIARY}; color: {T.TEXT_PRIMARY};"
            f" border: 1px solid {T.BG_TERTIARY}; border-radius: 6px;"
            " padding: 6px 12px; font-size: 11px; }}"
            f"QPushButton:checked {{ background: {T.BRAND}; color: {T.TEXT_PRIMARY};"
            f" border-color: {T.BRAND}; }}"
        )
        self._auto_refresh_btn.toggled.connect(self._toggle_auto_refresh)
        tb_layout.addWidget(self._auto_refresh_btn)

        main_layout.addWidget(toolbar)

        # Log viewer (QTextBrowser with monospace font)
        self._log_view = QTextBrowser()
        self._log_view.setFont(QFont("Consolas", 10))
        self._log_view.setStyleSheet(
            f"QTextBrowser {{ background: {T.BG_PRIMARY}; color: {T.TEXT_PRIMARY};"
            f" border: 1px solid {T.BG_TERTIARY}; border-radius: {T.R_SM}px;"
            " padding: 8px;"
            " font-family: 'Consolas', 'Courier New', monospace;"
            " font-size: 12px;"
        )
        main_layout.addWidget(self._log_view)

        # Status bar at bottom
        self._status_bar = QLabel("Ready")
        self._status_bar.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: {T.FS_SM}px;"
        )
        main_layout.addWidget(self._status_bar)

        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.AUTO_REFRESH_MS)
        self._refresh_timer.timeout.connect(self._fetch_logs)

    # ── Log Fetching ───────────────────────────────────────────────────────

    def _fetch_logs(self):
        """Fetch logs from the REST API and display them."""
        tail = self._tail_combo.currentText()
        url = f"{self._base_url}/{self._container_name}/logs?tail={tail}"

        try:
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                logs = data.get("logs", "")
                self._log_view.setPlainText(logs if logs else "(no logs)")
                self._status_indicator.set_status(True)
                self._status_label.setText("Connected")
                self._status_bar.setText(
                    f"Last updated: {self._now()} — tail={tail}"
                )
        except urllib.error.HTTPError as e:
            self._log_view.setPlainText(f"HTTP Error {e.code}: {e.reason}")
            self._status_indicator.set_status(False)
            self._status_label.setText("Error")
            self._status_bar.setText(f"Failed: HTTP {e.code}")
        except urllib.error.URLError as e:
            self._log_view.setPlainText(f"Connection failed: {e.reason}")
            self._status_indicator.set_status(False)
            self._status_label.setText("Disconnected")
            self._status_bar.setText(f"Failed: {e.reason}")
        except (json.JSONDecodeError, KeyError) as e:
            self._log_view.setPlainText(f"Invalid response: {e}")
            self._status_indicator.set_status(False)
            self._status_label.setText("Error")
            self._status_bar.setText("Failed: bad response")
        except Exception as e:
            self._log_view.setPlainText(f"Error: {e}")
            self._status_indicator.set_status(False)
            self._status_label.setText("Error")
            self._status_bar.setText(f"Failed: {e}")

    # ── Auto-Refresh ───────────────────────────────────────────────────────

    def _toggle_auto_refresh(self, enabled: bool):
        """Enable or disable auto-refresh."""
        self._auto_refresh_enabled = enabled
        if enabled:
            self._auto_refresh_btn.setText("Auto-refresh: ON")
            self._refresh_timer.start()
        else:
            self._auto_refresh_btn.setText("Auto-refresh: OFF")
            self._refresh_timer.stop()

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        """Return current time string."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    # ── Override ───────────────────────────────────────────────────────────

    def closeEvent(self, event: Any) -> None:
        """Stop the auto-refresh timer when the dialog closes."""
        self._refresh_timer.stop()
        super().closeEvent(event)

    def reject(self) -> None:
        """Stop timer on Esc / Cancel."""
        self._refresh_timer.stop()
        super().reject()

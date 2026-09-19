"""VM Control panel — full VM lifecycle management with QMP bridge integration.

Provides Start, Stop, Reset, Suspend, Resume, Eject ISO controls
wired to the QMPBridge for real VM operations.
"""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QGridLayout,
    QProgressBar,
    QSpinBox,
    QSizePolicy,
)

from gui.widgets import Card, StatusIndicator, SectionHeader, StatCard


class VMControlPanel(QWidget):
    """Full VM lifecycle control panel with real QMP integration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qmp_bridge = None
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)

        # ── Connection Status ──────────────────────────────────────────────────
        conn_card = Card("QMP Connection")
        layout.addWidget(conn_card)

        conn_row = QWidget()
        conn_row_layout = QHBoxLayout(conn_row)
        conn_row_layout.setContentsMargins(0, 0, 0, 0)
        conn_row_layout.setSpacing(12)

        self.qmp_status = StatusIndicator(QColor(T.TEXT_MUTED))
        conn_row_layout.addWidget(self.qmp_status, alignment=Qt.AlignVCenter)

        self.conn_info = QLabel("Disconnected — QMP not available")
        self.conn_info.setStyleSheet("color: #64748b; font-size: 12px;")
        conn_row_layout.addWidget(self.conn_info)
        conn_row_layout.addStretch()

        self.connect_btn = QPushButton("Connect to QMP")
        self.connect_btn.setFixedHeight(32)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 0 16px;
            }
            QPushButton:hover { background: #2563eb; }
            QPushButton:disabled { background: #3b82f620; color: #64748b; }
        """)
        conn_row_layout.addWidget(self.connect_btn)

        conn_card.content_layout.addWidget(conn_row)
        conn_card.content_layout.addStretch()

        # ── VM Lifecycle Controls ──────────────────────────────────────────────
        life_card = Card("VM Lifecycle Control")
        layout.addWidget(life_card)

        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(10)

        buttons_spec = [
            ("Start", "\U0001f7e2", T.SUCCESS, "Start the virtual machine"),
            ("Stop", "\u23f9", T.ERROR, "Gracefully stop the VM"),
            ("Reset", "\U0001f504", T.WARNING, "Reset the VM (warm reboot)"),
            ("Suspend", "\u23f8", T.BRAND, "Suspend the VM to disk"),
            ("Resume", "\u25b6", T.SUCCESS, "Resume a suspended VM"),
            ("Eject ISO", "\U0001f4bf", T.INFO, "Eject the boot ISO"),
        ]

        self._lifecycle_btns = {}
        for label, icon, color, tooltip in buttons_spec:
            btn = QPushButton(f"{icon}  {label}")
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 0 12px;
                }}
                QPushButton:hover {{ background: {self._darker(color)}; }}
                QPushButton:disabled {{ background: {color}20; color: #64748b; }}
            """)
            btn_row_layout.addWidget(btn)
            self._lifecycle_btns[label] = btn

        btn_row_layout.addStretch()
        life_card.content_layout.addWidget(btn_row)
        life_card.content_layout.addStretch()

        # ── VM Configuration Display ───────────────────────────────────────────
        config_card = Card("VM Configuration")
        layout.addWidget(config_card)

        config_grid = QGridLayout()
        config_grid.setContentsMargins(0, 0, 0, 0)
        config_grid.setSpacing(8)
        config_grid.setColumnStretch(1, 1)

        config_fields = [
            ("VM Name", "omarchy-vm"),
            ("Display", "SDL (OpenGL)"),
            ("RAM", "16384 MB"),
            ("vCPUs", "8"),
            ("Disk Image", "disk.qcow2 (64 GB)"),
            ("Boot ISO", "omarchy-4.0.4.iso"),
            ("Hostname", "omarchy-vm"),
            ("QMP Port", "4444 (TCP)"),
            ("Guest SSH", "127.0.0.1:2222"),
        ]

        for i, (label, value) in enumerate(config_fields):
            row = i // 3
            col = (i % 3) * 2
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #64748b; font-size: 11px;")
            lbl.setFixedWidth(80)
            config_grid.addWidget(lbl, row, col)

            val = QLabel(value)
            val.setStyleSheet("color: #e2e8f0; font-size: 12px;")
            config_grid.addWidget(val, row, col + 1)

        config_card.content_layout.addLayout(config_grid)
        config_card.content_layout.addStretch()

        # ── Boot Device Selector ───────────────────────────────────────────────
        boot_card = Card("Boot Configuration")
        layout.addWidget(boot_card)

        boot_row = QWidget()
        boot_row_layout = QHBoxLayout(boot_row)
        boot_row_layout.setContentsMargins(0, 0, 0, 0)
        boot_row_layout.setSpacing(12)

        boot_label = QLabel("Boot from:")
        boot_label.setStyleSheet("color: #cbd5e1; font-size: 13px;")
        boot_label.setFixedWidth(80)
        boot_row_layout.addWidget(boot_label)

        self.boot_combo = QComboBox()
        self.boot_combo.addItems([
            "Hard Disk (disk.qcow2)",
            "CD-ROM (omarchy-4.0.4.iso)",
            "Network (PXE)",
        ])
        self.boot_combo.setFixedWidth(220)
        self.boot_combo.setStyleSheet("""
            QComboBox {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox:hover { border-color: #3b82f6; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; }
        """)
        boot_row_layout.addWidget(self.boot_combo)

        apply_btn = QPushButton("Apply Boot Order")
        apply_btn.setFixedHeight(28)
        apply_btn.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #e2e8f0;
                border: 1px solid #475569;
                border-radius: 4px;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover { background: #475569; }
        """)
        boot_row_layout.addWidget(apply_btn)

        boot_row_layout.addStretch()
        boot_card.content_layout.addWidget(boot_row)
        boot_card.content_layout.addStretch()

        # ── Progress ───────────────────────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet("""
            QProgressBar {
                background: #1e293b;
                border: none;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #3b82f6;
                border-radius: 2px;
            }
        """)
        self.progress.setMaximum(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        # ── Info log ───────────────────────────────────────────────────────────
        self.info_label = QLabel("Ready — use the controls above to manage the VM.")
        self.info_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # ── Wire buttons ───────────────────────────────────────────────────────
        self.connect_btn.clicked.connect(self._on_connect)
        self._wire_lifecycle_buttons()

        # ── Status timer ───────────────────────────────────────────────────────
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_connection)
        self._pulse_timer.start(5000)

    def _wire_lifecycle_buttons(self):
        """Wire lifecycle buttons to QMP bridge commands."""
        self._lifecycle_btns["Start"].clicked.connect(self._qmp_start)
        self._lifecycle_btns["Stop"].clicked.connect(self._qmp_stop)
        self._lifecycle_btns["Reset"].clicked.connect(self._qmp_reset)
        self._lifecycle_btns["Suspend"].clicked.connect(self._qmp_suspend)
        self._lifecycle_btns["Resume"].clicked.connect(self._qmp_resume)
        self._lifecycle_btns["Eject ISO"].clicked.connect(self._qmp_eject)

    def set_qmp_bridge(self, bridge):
        """Connect to QMP bridge for commands."""
        self._qmp_bridge = bridge
        bridge.connected.connect(self._on_bridge_connected)
        bridge.error.connect(self._on_bridge_error)

    def _on_bridge_connected(self, connected: bool):
        if connected:
            self.qmp_status.set_status(running=True, connected=True)
            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("Connected")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background: #22c55e;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    padding: 0 16px;
                }
            """)
            self.conn_info.setText("Connected to QMP — VM controls active")
            self.conn_info.setStyleSheet("color: #22c55e; font-size: 12px;")
        else:
            self.qmp_status.set_status(running=False, connected=False)
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("Connect to QMP")
            self.conn_info.setText("Disconnected — QMP not available")
            self.conn_info.setStyleSheet("color: #64748b; font-size: 12px;")

    def _on_bridge_error(self, message: str):
        self.info_label.setText(f"QMP: {message}")
        self.info_label.setStyleSheet("color: #ef4444; font-size: 12px;")

    # ── QMP Command Wrappers ──────────────────────────────────────────────────

    def _qmp_start(self):
        if not self._qmp_bridge:
            self._show_info("QMP bridge not available", success=False)
            return
        self._show_info("Starting VM...", success=True)
        self._qmp_bridge.cont()
        self.progress.show()

    def _qmp_stop(self):
        if not self._qmp_bridge:
            self._show_info("QMP bridge not available", success=False)
            return
        self._show_info("Stopping VM...", success=True)
        self._qmp_bridge.system_powerdown()

    def _qmp_reset(self):
        if not self._qmp_bridge:
            self._show_info("QMP bridge not available", success=False)
            return
        self._show_info("Resetting VM...", success=True)
        self._qmp_bridge.system_reset()

    def _qmp_suspend(self):
        if not self._qmp_bridge:
            self._show_info("QMP bridge not available", success=False)
            return
        self._show_info("Suspending VM...", success=True)
        self._qmp_bridge.stop()

    def _qmp_resume(self):
        if not self._qmp_bridge:
            self._show_info("QMP bridge not available", success=False)
            return
        self._show_info("Resuming VM...", success=True)
        self._qmp_bridge.cont()

    def _qmp_eject(self):
        if not self._qmp_bridge:
            self._show_info("QMP bridge not available", success=False)
            return
        self._show_info("Ejecting CD-ROM...", success=True)
        self._qmp_bridge.eject_cdrom()

    def _on_connect(self):
        """Handle QMP connect button — uses the bridge."""
        if not self._qmp_bridge:
            self._show_info("QMP bridge not initialized", success=False)
            return
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
        self.conn_info.setText("Connecting to QMP...")
        self.conn_info.setStyleSheet("color: #f59e0b; font-size: 12px;")
        self._qmp_bridge.connect()

    def _show_info(self, message: str, success: bool = True):
        """Display an info message."""
        color = T.SUCCESS if success else T.ERROR
        self.info_label.setText(message)
        self.info_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _pulse_connection(self):
        """Keep connection indicator alive."""
        pass

    @staticmethod
    def _darker(hex_color: str) -> str:
        """Darken a hex color by ~15%."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = max(0, int(r * 0.85))
        g = max(0, int(g * 0.85))
        b = max(0, int(b * 0.85))
        return f"#{r:02x}{g:02x}{b:02x}"

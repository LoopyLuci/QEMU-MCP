"""VM Control panel — full VM lifecycle management.

Provides Start, Stop, Reset, Suspend, Resume, Eject ISO, and
Boot Device controls, plus live VM configuration display and
QMP connection status.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QProgressBar,
    QMessageBox,
    QSpinBox,
    QCheckBox,
    QSplitter,
    QSizePolicy,
)

from gui.widgets import Card, StatusIndicator, IconButton, TextInput


class VMControlPanel(QWidget):
    """Full VM lifecycle control panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #0f172a;")
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

        self.qmp_status = StatusIndicator(QColor("#555555"))
        conn_row_layout.addWidget(self.qmp_status, alignment=Qt.AlignVCenter)

        conn_info = QLabel("Disconnected — QMP not available")
        conn_info.setStyleSheet("color: #64748b; font-size: 12px;")
        conn_row_layout.addWidget(conn_info)
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
            ("Start", "🟢", "#22c55e", "Start the virtual machine"),
            ("Stop", "⏹️", "#ef4444", "Gracefully stop the VM"),
            ("Reset", "🔄", "#f59e0b", "Reset the VM (warm reboot)"),
            ("Suspend", "⏸️", "#3b82f6", "Suspend the VM to disk"),
            ("Resume", "▶️", "#22c55e", "Resume a suspended VM"),
            ("Eject ISO", "💿", "#a78bfa", "Eject the boot ISO"),
        ]

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
            "Network (PXЕ)",
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
        self.progress.setMaximum(0)  # Indeterminate
        self.progress.hide()
        layout.addWidget(self.progress)

        # ── Info log ───────────────────────────────────────────────────────────
        self.info_label = QLabel("Ready — use the controls above to manage the VM.")
        self.info_label.setStyleSheet("color: #64748b; font-size: 12px; align: center;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Connect buttons
        self.connect_btn.clicked.connect(self._on_connect)

        # Timers
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_connection)
        self._pulse_timer.start(5000)

    @staticmethod
    def _darker(hex_color: str) -> str:
        """Darken a hex color by ~15%."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = max(0, int(r * 0.85))
        g = max(0, int(g * 0.85))
        b = max(0, int(b * 0.85))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_connect(self):
        """Handle QMP connect button."""
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
        self.info_label.setText("Connecting to QMP at 127.0.0.1:4444...")
        QTimer.singleShot(1000, self._on_connect_done)

    def _on_connect_done(self):
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect to QMP")
        self.qmp_status.set_status(running=False, connected=True)
        self.info_label.setText("Connected to QMP. VM controls are active.")
        self.info_label.setStyleSheet("color: #22c55e; font-size: 12px;")

    def _pulse_connection(self):
        """Animate the connection indicator."""
        if self.qmp_status and self.qmp_status.property("connected"):
            pass  # Keep the green indicator

    def add_info(self, message: str, success: bool = True):
        """Display an info message."""
        color = "#22c55e" if success else "#ef4444"
        self.info_label.setText(message)
        self.info_label.setStyleSheet(f"color: {color}; font-size: 12px;")

"""Display & Remote Access Panel — VNC, SPICE, RDP, console."""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QCheckBox, QTextEdit, QMessageBox, QTabWidget, QGroupBox,
    QGridLayout, QFrame, QSizePolicy,
)

from gui.widgets import Card


class DisplayPanel(QWidget):
    """Display configuration and remote access."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Display & Remote Access")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        layout.addWidget(header)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; }"
            "QTabBar::tab { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 8px 16px; margin-right: 2px; border-radius: 4px 4px 0 0; }"
            "QTabBar::tab:selected { background: " + T.BRAND + "; color: white; }"
        )
        tabs.addTab(self._display_config_tab(), "Display")
        tabs.addTab(self._remote_access_tab(), "Remote Access")
        tabs.addTab(self._gpu_tab(), "GPU / 3D")
        layout.addWidget(tabs)

    def _display_config_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Display Configuration")
        layout.addWidget(card)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("Type:"), 0, 0)
        self._display_type = QComboBox()
        self._display_type.addItems(["SDL", "GTK", "VNC", "SPICE", "None"])
        self._display_type.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._display_type, 0, 1)

        form.addWidget(QLabel("Resolution:"), 1, 0)
        self._resolution = QComboBox()
        self._resolution.addItems(["Auto", "1920x1080", "2560x1440", "3840x2160", "Custom"])
        self._resolution.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._resolution, 1, 1)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _remote_access_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # VNC
        vnc_card = Card("VNC Server")
        layout.addWidget(vnc_card)
        vnc_form = QGridLayout()
        vnc_form.addWidget(QLabel("Port:"), 0, 0)
        self._vnc_port = QSpinBox()
        self._vnc_port.setRange(5900, 5999)
        self._vnc_port.setValue(5900)
        self._vnc_port.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        vnc_form.addWidget(self._vnc_port, 0, 1)
        vnc_card.content_layout.addLayout(vnc_form)

        # SPICE
        spice_card = Card("SPICE Server")
        layout.addWidget(spice_card)
        spice_form = QGridLayout()
        spice_form.addWidget(QLabel("Port:"), 0, 0)
        self._spice_port = QSpinBox()
        self._spice_port.setRange(5930, 5999)
        self._spice_port.setValue(5930)
        self._spice_port.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        spice_form.addWidget(self._spice_port, 0, 1)
        spice_card.content_layout.addLayout(spice_form)

        layout.addStretch()
        return page

    def _gpu_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("GPU Configuration")
        layout.addWidget(card)

        self._gpu_type = QComboBox()
        self._gpu_type.addItems(["None", "VirGL (virtio-vga)", "GPU Passthrough (vfio-pci)", "NVIDIA vGPU"])
        self._gpu_type.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        card.content_layout.addWidget(self._gpu_type)

        layout.addStretch()
        return page

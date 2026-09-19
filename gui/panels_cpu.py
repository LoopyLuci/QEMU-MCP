"""CPU & Memory Control Panel — hotplug, pinning, NUMA, limits."""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QCheckBox, QTextEdit, QMessageBox, QTabWidget, QGroupBox,
    QGridLayout, QFrame, QSizePolicy,
)

from gui.widgets import Card


class CPUControlPanel(QWidget):
    """CPU and memory hotplug, pinning, NUMA topology."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("CPU & Memory Control")
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
        tabs.addTab(self._cpu_tab(), "CPU")
        tabs.addTab(self._memory_tab(), "Memory")
        tabs.addTab(self._numa_tab(), "NUMA")
        layout.addWidget(tabs)

    def _cpu_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("CPU Configuration")
        layout.addWidget(card)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("Sockets:"), 0, 0)
        self._sockets = QSpinBox()
        self._sockets.setRange(1, 4)
        self._sockets.setValue(1)
        self._sockets.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._sockets, 0, 1)

        form.addWidget(QLabel("Cores per socket:"), 1, 0)
        self._cores = QSpinBox()
        self._cores.setRange(1, 128)
        self._cores.setValue(4)
        self._cores.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._cores, 1, 1)

        form.addWidget(QLabel("Threads per core:"), 2, 0)
        self._threads = QSpinBox()
        self._threads.setRange(1, 2)
        self._threads.setValue(1)
        self._threads.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._threads, 2, 1)

        self._host_passthrough = QCheckBox("Host CPU passthrough (host mode)")
        self._host_passthrough.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        form.addWidget(self._host_passthrough, 3, 0, 1, 2)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _memory_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Memory Configuration")
        layout.addWidget(card)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("Current Memory:"), 0, 0)
        self._mem_current = QSpinBox()
        self._mem_current.setRange(256, 131072)
        self._mem_current.setValue(4096)
        self._mem_current.setSuffix(" MB")
        self._mem_current.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._mem_current, 0, 1)

        self._mem_hotplug = QCheckBox("Enable memory hotplug")
        self._mem_hotplug.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        form.addWidget(self._mem_hotplug, 1, 0, 1, 2)

        self._balloon = QCheckBox("Enable virtio-balloon (dynamic memory)")
        self._balloon.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        form.addWidget(self._balloon, 2, 0, 1, 2)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _numa_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("NUMA Topology")
        layout.addWidget(card)

        self._numa_info = QTextEdit()
        self._numa_info.setReadOnly(True)
        self._numa_info.setStyleSheet("QTextEdit { background: #0d1117; color: #c9d1d9; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px; font-family: Consolas, monospace; font-size: 11px; }")
        self._numa_info.setText("""NUMA Node 0:
  CPUs: 0-3
  Memory: 4096 MB
  Distance: 10
""")
        card.content_layout.addWidget(self._numa_info)
        layout.addStretch()
        return page

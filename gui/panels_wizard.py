"""VM Creation Wizard — step-by-step VM provisioning."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QComboBox, QPushButton, QStackedWidget, QFileDialog, QCheckBox,
    QProgressBar, QTextEdit, QGroupBox, QFormLayout, QMessageBox,
)

from gui.widgets import Card


class VMCreationWizard(QWidget):
    """Step-by-step VM creation wizard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step = 0
        self._config = {
            "name": "new-vm",
            "os_type": "linux",
            "machine_type": "q35",
            "firmware": "ovmf",
            "cpus": 2,
            "ram_mb": 4096,
            "disk_size_gb": 40,
            "disk_format": "qcow2",
            "disk_cache": "writeback",
            "network_mode": "nat",
            "iso_path": "",
            "use_cloud_init": False,
            "display": "sdl",
            "enable_gl": True,
            "cpu_host_passthrough": False,
            "io_threads": 1,
        }
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("Create New Virtual Machine")
        header.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMaximum(5)
        self._progress.setValue(1)
        self._progress.setTextVisible(True)
        self._progress.setFormat("Step %v of 5")
        self._progress.setStyleSheet(
            "QProgressBar { background: " + T.BG_SECONDARY + "; border: none; border-radius: 4px; }"
            "QProgressBar::chunk { background: " + T.BRAND + "; border-radius: 4px; }"
        )
        layout.addWidget(self._progress)

        # Stacked widget for steps
        self._stack = QStackedWidget()
        self._stack.addWidget(self._step_identity())
        self._stack.addWidget(self._step_hardware())
        self._stack.addWidget(self._step_storage())
        self._stack.addWidget(self._step_network())
        self._stack.addWidget(self._step_confirm())
        layout.addWidget(self._stack)

        # Navigation buttons
        nav_row = QWidget()
        nav_layout = QHBoxLayout(nav_row)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        self._btn_back = QPushButton("← Back")
        self._btn_back.setFixedSize(100, 36)
        self._btn_back.setStyleSheet(
            "QPushButton { background: " + T.BG_SECONDARY + "; border: 1px solid " + T.BG_TERTIARY + ";"
            " border-radius: 6px; color: " + T.TEXT_SECONDARY + "; font-size: 13px; }"
            "QPushButton:hover { background: " + T.BG_TERTIARY + "; }"
            "QPushButton:disabled { color: " + T.TEXT_MUTED + "; }"
        )
        self._btn_back.clicked.connect(self._go_back)
        self._btn_back.setEnabled(False)
        nav_layout.addWidget(self._btn_back)

        nav_layout.addStretch()

        self._btn_next = QPushButton("Next →")
        self._btn_next.setFixedSize(100, 36)
        self._btn_next.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        self._btn_next.clicked.connect(self._go_next)
        nav_layout.addWidget(self._btn_next)

        self._btn_create = QPushButton("✓ Create VM")
        self._btn_create.setFixedSize(120, 36)
        self._btn_create.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        self._btn_create.clicked.connect(self._create_vm)
        self._btn_create.hide()
        nav_layout.addWidget(self._btn_create)

        layout.addWidget(nav_row)

    def _step_identity(self) -> QWidget:
        """Step 1: VM identity."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Virtual Machine Identity")
        layout.addWidget(card)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_input = QLineEdit(self._config["name"])
        self._name_input.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("VM Name:", self._name_input)

        self._os_combo = QComboBox()
        self._os_combo.addItems(["Linux", "Windows", "macOS", "BSD", "Other"])
        self._os_combo.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Operating System:", self._os_combo)

        self._machine_combo = QComboBox()
        self._machine_combo.addItems(["q35 (modern PC)", "pc (legacy PC)", "virt (ARM)"])
        self._machine_combo.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Machine Type:", self._machine_combo)

        self._firmware_combo = QComboBox()
        self._firmware_combo.addItems(["OVMF (UEFI)", "SeaBIOS (Legacy BIOS)"])
        self._firmware_combo.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Firmware:", self._firmware_combo)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _step_hardware(self) -> QWidget:
        """Step 2: CPU and memory."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("CPU & Memory")
        layout.addWidget(card)

        form = QFormLayout()
        form.setSpacing(10)

        self._cpu_spin = QSpinBox()
        self._cpu_spin.setRange(1, 128)
        self._cpu_spin.setValue(self._config["cpus"])
        self._cpu_spin.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Number of CPUs:", self._cpu_spin)

        self._ram_spin = QSpinBox()
        self._ram_spin.setRange(256, 131072)
        self._ram_spin.setSingleStep(512)
        self._ram_spin.setValue(self._config["ram_mb"])
        self._ram_spin.setSuffix(" MB")
        self._ram_spin.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Memory:", self._ram_spin)

        self._cpu_host_check = QCheckBox("Host CPU passthrough (host mode)")
        self._cpu_host_check.setStyleSheet("color: " + T.TEXT_SECONDARY + ";")
        form.addRow("", self._cpu_host_check)

        self._io_threads_spin = QSpinBox()
        self._io_threads_spin.setRange(1, 8)
        self._io_threads_spin.setValue(self._config["io_threads"])
        self._io_threads_spin.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("I/O Threads:", self._io_threads_spin)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _step_storage(self) -> QWidget:
        """Step 3: Disk configuration."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Storage Configuration")
        layout.addWidget(card)

        form = QFormLayout()
        form.setSpacing(10)

        self._disk_size_spin = QSpinBox()
        self._disk_size_spin.setRange(1, 2048)
        self._disk_size_spin.setValue(self._config["disk_size_gb"])
        self._disk_size_spin.setSuffix(" GB")
        self._disk_size_spin.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Disk Size:", self._disk_size_spin)

        self._disk_format_combo = QComboBox()
        self._disk_format_combo.addItems(["qcow2 (recommended)", "raw", "vmdk", "vhd"])
        self._disk_format_combo.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Disk Format:", self._disk_format_combo)

        self._disk_cache_combo = QComboBox()
        self._disk_cache_combo.addItems(["writeback", "writethrough", "none", "unsafe"])
        self._disk_cache_combo.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Cache Mode:", self._disk_cache_combo)

        # ISO selection
        iso_row = QWidget()
        iso_layout = QHBoxLayout(iso_row)
        iso_layout.setContentsMargins(0, 0, 0, 0)
        self._iso_path = QLineEdit()
        self._iso_path.setPlaceholderText("Optional: Select ISO for installation...")
        self._iso_path.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        iso_layout.addWidget(self._iso_path)
        iso_btn = QPushButton("Browse...")
        iso_btn.setFixedSize(80, 28)
        iso_btn.setStyleSheet("background: " + T.BG_SECONDARY + "; border: 1px solid " + T.BG_TERTIARY + ";"
            " border-radius: 4px; color: " + T.TEXT_SECONDARY + "; font-size: 11px;")
        iso_btn.clicked.connect(self._browse_iso)
        iso_layout.addWidget(iso_btn)
        form.addRow("Installation ISO:", iso_row)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _step_network(self) -> QWidget:
        """Step 4: Network configuration."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Network Configuration")
        layout.addWidget(card)

        form = QFormLayout()
        form.setSpacing(10)

        self._net_mode_combo = QComboBox()
        self._net_mode_combo.addItems(["NAT (user mode)", "Bridged", "Isolated"])
        self._net_mode_combo.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Network Mode:", self._net_mode_combo)

        self._port_fwd_text = QTextEdit()
        self._port_fwd_text.setPlaceholderText("Host Port → Guest Port (one per line, e.g., 2222 → 22)")
        self._port_fwd_text.setMaximumHeight(80)
        self._port_fwd_text.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addRow("Port Forwards:", self._port_fwd_text)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _step_confirm(self) -> QWidget:
        """Step 5: Review and confirm."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Review Configuration")
        layout.addWidget(card)

        self._summary = QTextEdit()
        self._summary.setReadOnly(True)
        self._summary.setStyleSheet("background: #0d1117; color: #c9d1d9;"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px;"
            " font-family: Consolas, monospace; font-size: 12px;")
        card.content_layout.addWidget(self._summary)

        layout.addStretch()
        return page

    def _browse_iso(self):
        """Open file dialog to select ISO."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Installation ISO", "",
            "ISO Images (*.iso);;All Files (*)"
        )
        if path:
            self._iso_path.setText(path)

    def _go_next(self):
        """Go to next step."""
        if self._step < 4:
            self._step += 1
            self._stack.setCurrentIndex(self._step)
            self._progress.setValue(self._step + 1)
            self._btn_back.setEnabled(True)
            if self._step == 4:
                self._btn_next.hide()
                self._btn_create.show()
                self._update_summary()

    def _go_back(self):
        """Go to previous step."""
        if self._step > 0:
            self._step -= 1
            self._stack.setCurrentIndex(self._step)
            self._progress.setValue(self._step + 1)
            self._btn_next.show()
            self._btn_create.hide()
            if self._step == 0:
                self._btn_back.setEnabled(False)

    def _update_summary(self):
        """Update summary text."""
        self._config.update({
            "name": self._name_input.text(),
            "os_type": self._os_combo.currentText().lower(),
            "machine_type": self._machine_combo.currentText().split()[0],
            "firmware": "ovmf" if "ovmf" in self._firmware_combo.currentText().lower() else "seabios",
            "cpus": self._cpu_spin.value(),
            "ram_mb": self._ram_spin.value(),
            "disk_size_gb": self._disk_size_spin.value(),
            "disk_format": self._disk_format_combo.currentText().split()[0],
            "disk_cache": self._disk_cache_combo.currentText(),
            "network_mode": self._net_mode_combo.currentText().split()[0].lower(),
            "iso_path": self._iso_path.text(),
            "cpu_host_passthrough": self._cpu_host_check.isChecked(),
            "io_threads": self._io_threads_spin.value(),
        })

        summary = f"""VM Configuration Summary
{'='*40}

Name: {self._config['name']}
OS Type: {self._config['os_type']}
Machine: {self._config['machine_type']}
Firmware: {self._config['firmware']}

CPUs: {self._config['cpus']}
RAM: {self._config['ram_mb']} MB
Host CPU Passthrough: {self._config['cpu_host_passthrough']}
I/O Threads: {self._config['io_threads']}

Disk Size: {self._config['disk_size_gb']} GB
Disk Format: {self._config['disk_format']}
Cache Mode: {self._config['disk_cache']}

Network: {self._config['network_mode']}
ISO: {self._config['iso_path'] or 'None'}
"""
        self._summary.setText(summary)

    def _create_vm(self):
        """Create the VM."""
        try:
            # Create disk
            vm_dir = Path.home() / "Virtual Machines" / self._config["name"]
            vm_dir.mkdir(parents=True, exist_ok=True)
            disk_path = vm_dir / "disk.qcow2"

            subprocess.run(
                ["qemu-img", "create", "-f", self._config["disk_format"],
                 str(disk_path), f"{self._config['disk_size_gb']}G"],
                check=True, capture_output=True, text=True, timeout=60
            )

            QMessageBox.information(
                self, "VM Created",
                f"Virtual machine '{self._config['name']}' created successfully!\n"
                f"Disk: {disk_path}\n"
                f"Size: {self._config['disk_size_gb']} GB"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create VM: {e}")

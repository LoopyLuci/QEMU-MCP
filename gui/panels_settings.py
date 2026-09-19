"""Settings panel — all configurable options grouped by category.

Provides form-based editing for QEMU binary, VM disk/ISO, RAM, CPUs,
display, SSH, QMP, logging, transport, and auth settings.
Changes are saved to .env and take effect on next server restart.
"""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QGridLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QTabWidget,
    QMessageBox,
    QFileDialog,
    QSizePolicy,
)

from gui.widgets import Card, TextInput


class SettingsPanel(QWidget):
    """All configurable settings organized by category."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #0f172a;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Tab widget for categories
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #64748b;
                border: 1px solid #334155;
                border-bottom: none;
                padding: 8px 16px;
                font-size: 12px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background: #1e3a5f;
                color: #60a5fa;
                border-color: #3b82f6;
            }
            QTabBar::tab:!selected:hover {
                background: #1e293b;
                color: #94a3b8;
            }
        """)
        layout.addWidget(self.tabs)

        # ── QEMU Settings Tab ──────────────────────────────────────────────────
        qemu_tab = QWidget()
        qemu_tab.setStyleSheet("background: #0f172a;")
        qemu_layout = QVBoxLayout(qemu_tab)
        qemu_layout.setContentsMargins(12, 12, 12, 12)
        qemu_layout.setSpacing(8)

        qemu_card = Card("QEMU Configuration")
        qemu_layout.addWidget(qemu_card)

        # QEMU Binary
        bin_row = QWidget()
        bin_row_layout = QHBoxLayout(bin_row)
        bin_row_layout.setContentsMargins(0, 0, 0, 0)
        bin_row_layout.setSpacing(8)
        bin_label = QLabel("QEMU Binary:")
        bin_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        bin_label.setFixedWidth(100)
        bin_row_layout.addWidget(bin_label)
        self.qemu_bin_input = TextInput("C:/Program Files/qemu/qemu-system-x86_64.exe")
        self.qemu_bin_input.setFixedWidth(360)
        bin_row_layout.addWidget(self.qemu_bin_input)
        bin_row_layout.addStretch()
        qemu_card.content_layout.addWidget(bin_row)

        # QEMU args
        args_row = QWidget()
        args_row_layout = QHBoxLayout(args_row)
        args_row_layout.setContentsMargins(0, 0, 0, 0)
        args_row_layout.setSpacing(8)
        args_label = QLabel("Extra QEMU Args:")
        args_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        args_label.setFixedWidth(100)
        args_row_layout.addWidget(args_label)
        self.qemu_args_input = TextInput("-machine q35,kernel_platform=")
        self.qemu_args_input.setFixedWidth(360)
        args_row_layout.addWidget(self.qemu_args_input)
        args_row_layout.addStretch()
        qemu_card.content_layout.addWidget(args_row)

        qemu_layout.addStretch()

        self.tabs.addTab(qemu_tab, "QEMU")

        # ── VM Settings Tab ────────────────────────────────────────────────────
        vm_tab = QWidget()
        vm_tab.setStyleSheet("background: #0f172a;")
        vm_layout = QVBoxLayout(vm_tab)
        vm_layout.setContentsMargins(12, 12, 12, 12)
        vm_layout.setSpacing(8)

        vm_card = Card("Virtual Machine Configuration")
        vm_layout.addWidget(vm_card)

        # VM Name
        name_row = QWidget()
        name_row_layout = QHBoxLayout(name_row)
        name_row_layout.setContentsMargins(0, 0, 0, 0)
        name_row_layout.setSpacing(8)
        name_label = QLabel("VM Name:")
        name_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        name_label.setFixedWidth(100)
        name_row_layout.addWidget(name_label)
        self.vm_name_input = TextInput("omarchy-vm")
        self.vm_name_input.setFixedWidth(200)
        name_row_layout.addWidget(self.vm_name_input)
        name_row_layout.addStretch()
        vm_card.content_layout.addWidget(name_row)

        # Disk
        disk_row = QWidget()
        disk_row_layout = QHBoxLayout(disk_row)
        disk_row_layout.setContentsMargins(0, 0, 0, 0)
        disk_row_layout.setSpacing(8)
        disk_label = QLabel("Disk Path:")
        disk_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        disk_label.setFixedWidth(100)
        disk_row_layout.addWidget(disk_label)
        self.disk_input = TextInput("C:/Users/Server/Virtual Machines/omarchy-vm/disk.qcow2")
        self.disk_input.setFixedWidth(360)
        disk_row_layout.addWidget(self.disk_input)
        disk_row_layout.addStretch()
        vm_card.content_layout.addWidget(disk_row)

        # ISO
        iso_row = QWidget()
        iso_row_layout = QHBoxLayout(iso_row)
        iso_row_layout.setContentsMargins(0, 0, 0, 0)
        iso_row_layout.setSpacing(8)
        iso_label = QLabel("ISO Path:")
        iso_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        iso_label.setFixedWidth(100)
        iso_row_layout.addWidget(iso_label)
        self.iso_input = TextInput("C:/Projects/Omarchy/vm-setup/omarchy-4.0.4.iso")
        self.iso_input.setFixedWidth(360)
        iso_row_layout.addWidget(self.iso_input)
        iso_row_layout.addStretch()
        vm_card.content_layout.addWidget(iso_row)

        # RAM
        ram_row = QWidget()
        ram_row_layout = QHBoxLayout(ram_row)
        ram_row_layout.setContentsMargins(0, 0, 0, 0)
        ram_row_layout.setSpacing(8)
        ram_label = QLabel("RAM (MB):")
        ram_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        ram_label.setFixedWidth(100)
        ram_row_layout.addWidget(ram_label)
        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(512, 65536)
        self.ram_spin.setValue(16384)
        self.ram_spin.setFixedWidth(120)
        self.ram_spin.setStyleSheet("""
            QSpinBox {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QSpinBox:hover { border-color: #3b82f6; }
        """)
        ram_row_layout.addWidget(self.ram_spin)
        ram_row_layout.addStretch()
        vm_card.content_layout.addWidget(ram_row)

        # CPUs
        cpu_row = QWidget()
        cpu_row_layout = QHBoxLayout(cpu_row)
        cpu_row_layout.setContentsMargins(0, 0, 0, 0)
        cpu_row_layout.setSpacing(8)
        cpu_label = QLabel("vCPUs:")
        cpu_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        cpu_label.setFixedWidth(100)
        cpu_row_layout.addWidget(cpu_label)
        self.cpu_spin = QSpinBox()
        self.cpu_spin.setRange(1, 128)
        self.cpu_spin.setValue(8)
        self.cpu_spin.setFixedWidth(120)
        self.cpu_spin.setStyleSheet("""
            QSpinBox {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QSpinBox:hover { border-color: #3b82f6; }
        """)
        cpu_row_layout.addWidget(self.cpu_spin)
        cpu_row_layout.addStretch()
        vm_card.content_layout.addWidget(cpu_row)

        # Hostname
        host_row = QWidget()
        host_row_layout = QHBoxLayout(host_row)
        host_row_layout.setContentsMargins(0, 0, 0, 0)
        host_row_layout.setSpacing(8)
        host_label = QLabel("Hostname:")
        host_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        host_label.setFixedWidth(100)
        host_row_layout.addWidget(host_label)
        self.hostname_input = TextInput("omarchy-vm")
        self.hostname_input.setFixedWidth(200)
        host_row_layout.addWidget(self.hostname_input)
        host_row_layout.addStretch()
        vm_card.content_layout.addWidget(host_row)

        vm_layout.addStretch()
        self.tabs.addTab(vm_tab, "VM")

        # ── Display Tab ────────────────────────────────────────────────────────
        disp_tab = QWidget()
        disp_tab.setStyleSheet("background: #0f172a;")
        disp_layout = QVBoxLayout(disp_tab)
        disp_layout.setContentsMargins(12, 12, 12, 12)
        disp_layout.setSpacing(8)

        disp_card = Card("Display Configuration")
        disp_layout.addWidget(disp_card)

        # Display type
        disp_row = QWidget()
        disp_row_layout = QHBoxLayout(disp_row)
        disp_row_layout.setContentsMargins(0, 0, 0, 0)
        disp_row_layout.setSpacing(8)
        disp_label = QLabel("Display Type:")
        disp_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        disp_label.setFixedWidth(100)
        disp_row_layout.addWidget(disp_label)
        self.display_combo = QComboBox()
        self.display_combo.addItems(["SDL", "GTK", "VNC", "Spice", "None"])
        self.display_combo.setCurrentText("SDL")
        self.display_combo.setFixedWidth(140)
        self.display_combo.setStyleSheet("""
            QComboBox {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox:hover { border-color: #3b82f6; }
        """)
        disp_row_layout.addWidget(self.display_combo)
        disp_row_layout.addStretch()
        disp_card.content_layout.addWidget(disp_row)

        # OpenGL
        gl_row = QWidget()
        gl_row_layout = QHBoxLayout(gl_row)
        gl_row_layout.setContentsMargins(0, 0, 0, 0)
        gl_row_layout.setSpacing(8)
        gl_label = QLabel("OpenGL:")
        gl_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        gl_label.setFixedWidth(100)
        gl_row_layout.addWidget(gl_label)
        self.gl_check = QCheckBox("Enable OpenGL")
        self.gl_check.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self.gl_check.setChecked(True)
        gl_row_layout.addWidget(self.gl_check)
        gl_row_layout.addStretch()
        disp_card.content_layout.addWidget(gl_row)

        # Auto-eject ISO
        eject_row = QWidget()
        eject_row_layout = QHBoxLayout(eject_row)
        eject_row_layout.setContentsMargins(0, 0, 0, 0)
        eject_row_layout.setSpacing(8)
        eject_label = QLabel("Auto-eject ISO:")
        eject_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        eject_label.setFixedWidth(100)
        eject_row_layout.addWidget(eject_label)
        self.eject_check = QCheckBox("Auto-eject CD-ROM after boot")
        self.eject_check.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self.eject_check.setChecked(True)
        eject_row_layout.addWidget(self.eject_check)
        eject_row_layout.addStretch()
        disp_card.content_layout.addWidget(eject_row)

        disp_layout.addStretch()
        self.tabs.addTab(disp_tab, "Display")

        # ── Network Tab ─────────────────────────────────────────────────────────
        net_tab = QWidget()
        net_tab.setStyleSheet("background: #0f172a;")
        net_layout = QVBoxLayout(net_tab)
        net_layout.setContentsMargins(12, 12, 12, 12)
        net_layout.setSpacing(8)

        net_card = Card("Network Configuration")
        net_layout.addWidget(net_card)

        # SSH Host
        ssh_row = QWidget()
        ssh_row_layout = QHBoxLayout(ssh_row)
        ssh_row_layout.setContentsMargins(0, 0, 0, 0)
        ssh_row_layout.setSpacing(8)
        ssh_label = QLabel("SSH Host:")
        ssh_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        ssh_label.setFixedWidth(100)
        ssh_row_layout.addWidget(ssh_label)
        self.ssh_host_input = TextInput("127.0.0.1")
        self.ssh_host_input.setFixedWidth(200)
        ssh_row_layout.addWidget(self.ssh_host_input)
        ssh_row_layout.addStretch()
        net_card.content_layout.addWidget(ssh_row)

        # SSH Port
        ssh_port_row = QWidget()
        ssh_port_row_layout = QHBoxLayout(ssh_port_row)
        ssh_port_row_layout.setContentsMargins(0, 0, 0, 0)
        ssh_port_row_layout.setSpacing(8)
        ssh_port_label = QLabel("SSH Port:")
        ssh_port_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        ssh_port_label.setFixedWidth(100)
        ssh_port_row_layout.addWidget(ssh_port_label)
        self.ssh_port_spin = QSpinBox()
        self.ssh_port_spin.setRange(1, 65535)
        self.ssh_port_spin.setValue(2222)
        self.ssh_port_spin.setFixedWidth(120)
        self.ssh_port_spin.setStyleSheet("""
            QSpinBox {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QSpinBox:hover { border-color: #3b82f6; }
        """)
        ssh_port_row_layout.addWidget(self.ssh_port_spin)
        ssh_port_row_layout.addStretch()
        net_card.content_layout.addWidget(ssh_port_row)

        # Guest username
        guest_user_row = QWidget()
        guest_user_row_layout = QHBoxLayout(guest_user_row)
        guest_user_row_layout.setContentsMargins(0, 0, 0, 0)
        guest_user_row_layout.setSpacing(8)
        guest_user_label = QLabel("Guest Username:")
        guest_user_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        guest_user_label.setFixedWidth(100)
        guest_user_row_layout.addWidget(guest_user_label)
        self.guest_user_input = TextInput("omarchyvm")
        self.guest_user_input.setFixedWidth(200)
        guest_user_row_layout.addWidget(self.guest_user_input)
        guest_user_row_layout.addStretch()
        net_card.content_layout.addWidget(guest_user_row)

        net_layout.addStretch()
        self.tabs.addTab(net_tab, "Network")

        # ── Logging Tab ────────────────────────────────────────────────────────
        log_tab = QWidget()
        log_tab.setStyleSheet("background: #0f172a;")
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(12, 12, 12, 12)
        log_layout.setSpacing(8)

        log_card = Card("Logging Configuration")
        log_layout.addWidget(log_card)

        # Log Level
        level_row = QWidget()
        level_row_layout = QHBoxLayout(level_row)
        level_row_layout.setContentsMargins(0, 0, 0, 0)
        level_row_layout.setSpacing(8)
        level_label = QLabel("Log Level:")
        level_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        level_label.setFixedWidth(100)
        level_row_layout.addWidget(level_label)
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.setCurrentText("INFO")
        self.log_level_combo.setFixedWidth(140)
        self.log_level_combo.setStyleSheet("""
            QComboBox {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox:hover { border-color: #3b82f6; }
        """)
        level_row_layout.addWidget(self.log_level_combo)
        level_row_layout.addStretch()
        log_card.content_layout.addWidget(level_row)

        # Log File
        log_file_row = QWidget()
        log_file_row_layout = QHBoxLayout(log_file_row)
        log_file_row_layout.setContentsMargins(0, 0, 0, 0)
        log_file_row_layout.setSpacing(8)
        log_file_label = QLabel("Log File:")
        log_file_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        log_file_label.setFixedWidth(100)
        log_file_row_layout.addWidget(log_file_label)
        self.log_file_input = TextInput("")
        self.log_file_input.setFixedWidth(360)
        log_file_row_layout.addWidget(self.log_file_input)
        log_file_row_layout.addStretch()
        log_card.content_layout.addWidget(log_file_row)

        log_layout.addStretch()
        self.tabs.addTab(log_tab, "Logging")

        # ── Authentication Tab ─────────────────────────────────────────────────
        auth_tab = QWidget()
        auth_tab.setStyleSheet("background: #0f172a;")
        auth_layout = QVBoxLayout(auth_tab)
        auth_layout.setContentsMargins(12, 12, 12, 12)
        auth_layout.setSpacing(8)

        auth_card = Card("Authentication Configuration")
        auth_layout.addWidget(auth_card)

        # Auth Method
        auth_method_row = QWidget()
        auth_method_row_layout = QHBoxLayout(auth_method_row)
        auth_method_row_layout.setContentsMargins(0, 0, 0, 0)
        auth_method_row_layout.setSpacing(8)
        auth_method_label = QLabel("Auth Method:")
        auth_method_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        auth_method_label.setFixedWidth(100)
        auth_method_row_layout.addWidget(auth_method_label)
        self.auth_method_combo = QComboBox()
        self.auth_method_combo.addItems(["api_key", "none", "jwt"])
        self.auth_method_combo.setCurrentText("api_key")
        self.auth_method_combo.setFixedWidth(140)
        self.auth_method_combo.setStyleSheet("""
            QComboBox {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QComboBox:hover { border-color: #3b82f6; }
        """)
        auth_method_row_layout.addWidget(self.auth_method_combo)
        auth_method_row_layout.addStretch()
        auth_card.content_layout.addWidget(auth_method_row)

        # API Key (placeholder — stored securely)
        api_key_row = QWidget()
        api_key_row_layout = QHBoxLayout(api_key_row)
        api_key_row_layout.setContentsMargins(0, 0, 0, 0)
        api_key_row_layout.setSpacing(8)
        api_key_label = QLabel("API Key:")
        api_key_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        api_key_label.setFixedWidth(100)
        api_key_row_layout.addWidget(api_key_label)
        api_key_status = QLabel("Stored securely — use Security tab")
        api_key_status.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
        auth_method_row_layout.addWidget(api_key_status)
        api_key_row_layout.addStretch()
        auth_card.content_layout.addWidget(api_key_row)

        auth_layout.addStretch()
        self.tabs.addTab(auth_tab, "Auth")

        # ── Save Button ────────────────────────────────────────────────────────
        save_card = Card("")
        save_card.setFixedHeight(50)
        layout.addWidget(save_card)

        save_row = QWidget()
        save_row_layout = QHBoxLayout(save_row)
        save_row_layout.setContentsMargins(0, 0, 0, 0)
        save_row_layout.setSpacing(12)

        save_btn = QPushButton("Save Settings")
        save_btn.setFixedHeight(32)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #22c55e;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover { background: #16a34a; }
        """)
        save_row_layout.addWidget(save_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setFixedHeight(32)
        reset_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover { color: #94a3b8; }
        """)
        save_row_layout.addWidget(reset_btn)

        save_row_layout.addStretch()
        save_card.content_layout.addWidget(save_row)
        save_card.content_layout.addStretch()

        refresh_btn = QPushButton("Refresh from .env")
        refresh_btn.setFixedHeight(32)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 12px;
                padding: 0 16px;
            }
            QPushButton:hover { color: #94a3b8; border-color: #475569; }
        """)
        save_row_layout.addWidget(refresh_btn)

        save_btn.clicked.connect(self._save_settings)
        reset_btn.clicked.connect(self._reset_defaults)
        refresh_btn.clicked.connect(self._load_from_env)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.status_label)

    def _load_from_env(self):
        """Reload all fields from the current .env file."""
        from pathlib import Path
        import os

        env_path = Path(".env")
        if not env_path.exists():
            self.status_label.setText("✗ No .env file found")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 12px;")
            return

        # Load into a fresh settings object to get processed values
        from vm_mcp.config import VmMCPSettings

        # Temporarily point settings at this env file
        os.environ["VM_MCP_ENV_FILE"] = str(env_path.resolve())
        settings = VmMCPSettings()

        self.qemu_bin_input.setText(settings.qemu_binary)
        self.qemu_args_input.setText(settings.qemu_extra_args or "")
        self.vm_name_input.setText(settings.vm_name)
        self.disk_input.setText(settings.vm_disk_path)
        self.iso_input.setText(settings.vm_iso_path)
        self.ram_spin.setValue(settings.vm_ram_mb)
        self.cpu_spin.setValue(settings.vm_cpus)
        self.hostname_input.setText(settings.vm_hostname)
        self.display_combo.setCurrentText(settings.display.upper() if settings.display else "SDL")
        self.gl_check.setChecked(settings.gl)
        self.eject_check.setChecked(settings.auto_eject_iso)
        self.ssh_host_input.setText(settings.ssh_host)
        self.ssh_port_spin.setValue(settings.ssh_port)
        self.guest_user_input.setText(settings.ssh_username)
        self.log_level_combo.setCurrentText(getattr(settings, "log_level", "INFO").upper())
        self.log_file_input.setText(settings.log_file or "")
        auth = getattr(settings, "auth_method", "api_key").lower()
        if auth in ("api_key", "none", "jwt"):
            self.auth_method_combo.setCurrentText(auth)
        self.status_label.setText("✓ Settings reloaded from .env")
        self.status_label.setStyleSheet("color: #22c55e; font-size: 12px;")
        # Remove the env override so subsequent loads use the default
        os.environ.pop("VM_MCP_ENV_FILE", None)

    def _save_settings(self):
        """Save all settings to .env and config."""
        from pathlib import Path
        from vm_mcp.config import VmMCPSettings

        env_path = Path(".env")
        settings = {}

        # QEMU
        settings["QEMU_BINARY"] = self.qemu_bin_input.text()
        settings["QEMU_EXTRA_ARGS"] = self.qemu_args_input.text()

        # VM
        settings["VM_NAME"] = self.vm_name_input.text()
        settings["VM_DISK"] = self.disk_input.text()
        settings["VM_ISO"] = self.iso_input.text()
        settings["VM_RAM_MB"] = str(self.ram_spin.value())
        settings["VM_CPUS"] = str(self.cpu_spin.value())
        settings["VM_HOSTNAME"] = self.hostname_input.text()

        # Display
        settings["DISPLAY"] = self.display_combo.currentText()
        settings["OPENGL"] = "1" if self.gl_check.isChecked() else "0"
        settings["AUTO_EJECT_ISO"] = "1" if self.eject_check.isChecked() else "0"

        # Network
        settings["SSH_HOST"] = self.ssh_host_input.text()
        settings["SSH_PORT"] = str(self.ssh_port_spin.value())
        settings["SSH_USERNAME"] = self.guest_user_input.text()

        # Logging
        settings["LOG_LEVEL"] = self.log_level_combo.currentText()

        # Auth
        settings["AUTH_METHOD"] = self.auth_method_combo.currentText()

        try:
            # Read existing .env
            existing = {}
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        existing[key.strip()] = val.strip()

            # Merge
            existing.update(settings)

            # Write back
            lines = ["# QEMU-MCP Configuration — auto-saved from GUI"]
            for key, val in sorted(existing.items()):
                lines.append(f'{key}="{val}"')
            env_path.write_text("\n".join(lines) + "\n")
            env_path.chmod(0o600)

            self.status_label.setText("✓ Settings saved to .env")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 12px;")
            QMessageBox.information(self, "Settings Saved", "Settings have been saved to .env. Restart the server to apply changes.")
        except Exception as e:
            self.status_label.setText(f"✗ Failed to save: {e}")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 12px;")
            QMessageBox.critical(self, "Save Failed", f"Could not save settings: {e}")

    def _reset_defaults(self):
        """Reset all fields to default values."""
        self.qemu_bin_input.setText("C:/Program Files/qemu/qemu-system-x86_64.exe")
        self.qemu_args_input.setText("-machine q35,kernel_platform=")
        self.vm_name_input.setText("omarchy-vm")
        self.disk_input.setText("C:/Users/Server/Virtual Machines/omarchy-vm/disk.qcow2")
        self.iso_input.setText("C:/Projects/Omarchy/vm-setup/omarchy-4.0.4.iso")
        self.ram_spin.setValue(16384)
        self.cpu_spin.setValue(8)
        self.hostname_input.setText("omarchy-vm")
        self.display_combo.setCurrentText("SDL")
        self.gl_check.setChecked(True)
        self.eject_check.setChecked(True)
        self.ssh_host_input.setText("127.0.0.1")
        self.ssh_port_spin.setValue(2222)
        self.guest_user_input.setText("omarchyvm")
        self.log_level_combo.setCurrentText("INFO")
        self.log_file_input.setText("")
        self.auth_method_combo.setCurrentText("api_key")
        self.status_label.setText("Settings reset to defaults")
        self.status_label.setStyleSheet("color: #f59e0b; font-size: 12px;")

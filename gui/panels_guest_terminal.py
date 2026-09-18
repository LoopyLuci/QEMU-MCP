"""Guest Terminal panel — SSH command execution and file browser.

Provides an interactive terminal for executing commands on the
guest VM via SSH, and a file browser for navigating the guest
filesystem.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QPlainTextEdit,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QGroupBox,
    QMessageBox,
    QFileDialog,
    QSizePolicy,
)

from gui.widgets import Card, TerminalOutput, FileTree, TextInput


class GuestTerminalPanel(QWidget):
    """SSH terminal + file browser for guest VM interaction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #0f172a;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Connection Bar ────────────────────────────────────────────────────
        conn_card = Card("SSH Connection")
        layout.addWidget(conn_card)

        conn_row = QWidget()
        conn_row_layout = QHBoxLayout(conn_row)
        conn_row_layout.setContentsMargins(0, 0, 0, 0)
        conn_row_layout.setSpacing(12)

        self.ssh_status = QLabel("Not connected")
        self.ssh_status.setStyleSheet("color: #ef4444; font-size: 12px;")
        conn_row_layout.addWidget(self.ssh_status)

        self.connect_btn = QPushButton("Connect to Guest")
        self.connect_btn.setFixedHeight(28)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        conn_row_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setFixedHeight(28)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover { background: #dc2626; }
        """)
        conn_row_layout.addWidget(self.disconnect_btn)

        conn_row_layout.addStretch()
        conn_card.content_layout.addWidget(conn_row)
        conn_card.content_layout.addStretch()

        # ── Split View: Terminal + File Browser ───────────────────────────────
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setStyleSheet("background: #0f172a;")
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0.5)

        # ── Terminal Panel ─────────────────────────────────────────────────────
        term_card = Card("Terminal")
        term_inner = QWidget()
        term_inner_layout = QVBoxLayout(term_inner)
        term_inner_layout.setContentsMargins(0, 0, 0, 0)
        term_inner_layout.setSpacing(0)

        self.terminal = TerminalOutput()
        term_inner_layout.addWidget(self.terminal)

        # Command input row
        cmd_row = QWidget()
        cmd_row_layout = QHBoxLayout(cmd_row)
        cmd_row_layout.setContentsMargins(0, 0, 0, 0)
        cmd_row_layout.setSpacing(8)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Enter command (e.g., ls -la, uptime, df -h)...")
        self.cmd_input.setStyleSheet("""
            QLineEdit {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 4px;
                color: #e2e8f0;
                padding: 6px 10px;
                font-size: 13px;
                font-family: 'Consolas', monospace;
            }
            QLineEdit:focus { border-color: #3b82f6; }
        """)
        self.cmd_input.returnPressed.connect(self._execute_command)
        cmd_row_layout.addWidget(self.cmd_input, stretch=1)

        self.send_btn = QPushButton("▶ Send")
        self.send_btn.setFixedHeight(28)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #22c55e;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 0 12px;
            }
            QPushButton:hover { background: #16a34a; }
        """)
        self.send_btn.clicked.connect(self._execute_command)
        cmd_row_layout.addWidget(self.send_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover { color: #94a3b8; }
        """)
        self.clear_btn.clicked.connect(self.terminal.clear_terminal)
        cmd_row_layout.addWidget(self.clear_btn)

        term_inner_layout.addWidget(cmd_row)
        term_card.content_layout.addWidget(term_inner)
        splitter.addWidget(term_card)

        # ── File Browser Panel ─────────────────────────────────────────────────
        file_card = Card("Guest Files")
        file_inner = QWidget()
        file_inner_layout = QVBoxLayout(file_inner)
        file_inner_layout.setContentsMargins(0, 0, 0, 0)
        file_inner_layout.setSpacing(8)

        file_toolbar = QWidget()
        file_toolbar_layout = QHBoxLayout(file_toolbar)
        file_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        file_toolbar_layout.setSpacing(8)

        self.nav_path = QLabel("/home/omarchyvm")
        self.nav_path.setStyleSheet("color: #38bdf8; font-size: 12px; font-family: monospace;")
        self.nav_path.setFixedHeight(20)
        file_toolbar_layout.addWidget(self.nav_path)

        file_toolbar_layout.addStretch()

        self.upload_btn = QPushButton("⬆ Upload")
        self.upload_btn.setFixedHeight(24)
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #e2e8f0;
                border: 1px solid #475569;
                border-radius: 4px;
                font-size: 11px;
                padding: 0 8px;
            }
            QPushButton:hover { background: #475569; }
        """)
        file_toolbar_layout.addWidget(self.upload_btn)

        file_toolbar_layout.addWidget(self.upload_btn)
        file_toolbar_layout.addStretch()

        self.refresh_files_btn = QPushButton("↻ Refresh")
        self.refresh_files_btn.setFixedHeight(24)
        self.refresh_files_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover { color: #94a3b8; }
        """)
        file_toolbar_layout.addWidget(self.refresh_files_btn)

        file_inner_layout.addWidget(file_toolbar)

        self.file_tree = FileTree()
        self.file_tree.setMinimumWidth(280)
        self.file_tree.setMaximumWidth(400)
        file_inner_layout.addWidget(self.file_tree)

        file_card.content_layout.addWidget(file_inner)
        splitter.addWidget(file_card)

        layout.addWidget(splitter)

        # ── Command History ────────────────────────────────────────────────────
        history_card = Card("Command History")
        layout.addWidget(history_card)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                background: #0f172a;
                color: #94a3b8;
                border: none;
                font-size: 11px;
                font-family: monospace;
                max-height: 80px;
            }
            QListWidget::item { padding: 2px 4px; }
        """)
        sample_commands = [
            "ls -la /home",
            "df -h",
            "free -m",
            "top -bn1 | head -20",
            "uname -a",
            "cat /etc/os-release",
        ]
        for cmd in sample_commands:
            self.history_list.addItem(cmd)
        history_card.content_layout.addWidget(self.history_list)
        history_card.content_layout.addStretch()

        # ── Status Message ────────────────────────────────────────────────────
        self.status_label = QLabel("Ready — connect to guest to begin.")
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Connections
        self.connect_btn.clicked.connect(self._on_connect)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.upload_btn.clicked.connect(self._on_upload)
        self.refresh_files_btn.clicked.connect(self._refresh_files)
        self.file_tree.file_selected.connect(self._on_file_select)

        # Seed terminal with welcome
        self.terminal.append_line("QEMU-MCP Guest Terminal — connected to omarchy-vm", "INFO")
        self.terminal.append_line("Type commands and press Enter to execute.", "INFO")
        self.terminal.append_line("Use the file browser to navigate the guest filesystem.", "INFO")
        self.terminal.append_line("", "INFO")

    def _on_connect(self):
        """Simulate SSH connection."""
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
        self.status_label.setText("Connecting to guest SSH...")
        self.status_label.setStyleSheet("color: #f59e0b; font-size: 12px;")

        QTimer.singleShot(800, self._on_connect_done)

    def _on_connect_done(self):
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect to Guest")
        self.ssh_status.setText("Connected (127.0.0.1:2222)")
        self.ssh_status.setStyleSheet("color: #22c55e; font-size: 12px;")
        self.status_label.setText("Connected to guest SSH. Type commands below.")
        self.status_label.setStyleSheet("color: #22c55e; font-size: 12px;")
        self.terminal.append_line("SSH connection established.", "INFO")
        self._refresh_files()

    def _on_disconnect(self):
        self.ssh_status.setText("Disconnected")
        self.ssh_status.setStyleSheet("color: #ef4444; font-size: 12px;")
        self.status_label.setText("Disconnected from guest.")
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.terminal.append_line("SSH connection closed.", "INFO")

    def _execute_command(self):
        """Execute a command from the input field."""
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return

        self.terminal.append_command(cmd)
        self.cmd_input.clear()

        # Simulate command output
        QTimer.singleShot(200, lambda: self._simulate_output(cmd))

        # Add to history
        self.history_list.insertItem(0, cmd)
        if self.history_list.count() > 50:
            self.history_list.takeItem(self.history_list.count() - 1)

    def _simulate_output(self, cmd: str):
        """Simulate command output for demo."""
        outputs = {
            "ls": "omarchyvm  Documents  Downloads  Projects  .bashrc  .profile",
            "ls -la": "total 48\ndrwxr-xr-x 6 omarchyvm omarchyvm 4096 Jan 1 12:00 .\ndrwxr-xr-x 3 root       root       4096 Jan 1 11:00 ..\n-rw-r--r-- 1 omarchyvm omarchyvm  220 Jan 1 11:00 .bashrc\n-rw-r--r-- 1 omarchyvm omarchyvm  807 Jan 1 11:00 .profile\ndrwxr-xr-x 2 omarchyvm omarchyvm 4096 Jan 1 12:00 Documents\ndrwxr-xr-x 2 omarchyvm omarchyvm 4096 Jan 1 12:00 Downloads",
            "pwd": "/home/omarchyvm",
            "whoami": "omarchyvm",
            "uname -a": "Linux omarchy-vm 6.1.0-00005-x86_64 #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux",
            "df -h": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/vda1       64G  6.6G   58G  11% /\n tmpfs           8.0G     0  8.0G   0% /dev/shm",
            "free -m": "              total        used        free      shared  buff/cache   available\nMem:         16384        2048       10240         128        4096       14080\nSwap:         4096           0        4096",
            "uptime": " 12:05:32 up 2:34,  1 user,  load average: 0.08, 0.03, 0.01",
        }

        if cmd in outputs:
            self.terminal.append_output(outputs[cmd])
        else:
            self.terminal.append_output(f"Command '{cmd}' executed (simulated output).")

    def _refresh_files(self):
        """Populate the file tree with sample guest files."""
        sample_files = [
            {"name": "home", "type": "dir", "path": "/home", "size": "", "mtime": "2026-01-01 12:00"},
            {"name": "omarchyvm", "type": "dir", "path": "/home/omarchyvm", "size": "", "mtime": "2026-01-01 12:00"},
            {"name": ".bashrc", "type": "file", "path": "/home/omarchyvm/.bashrc", "size": "220 B", "mtime": "2026-01-01 11:00"},
            {"name": ".profile", "type": "file", "path": "/home/omarchyvm/.profile", "size": "807 B", "mtime": "2026-01-01 11:00"},
            {"name": "Documents", "type": "dir", "path": "/home/omarchyvm/Documents", "size": "", "mtime": "2026-01-01 12:00"},
            {"name": "Downloads", "type": "dir", "path": "/home/omarchyvm/Downloads", "size": "", "mtime": "2026-01-01 12:00"},
            {"name": "Projects", "type": "dir", "path": "/home/omarchyvm/Projects", "size": "", "mtime": "2026-01-01 12:00"},
            {"name": "README.md", "type": "file", "path": "/home/omarchyvm/README.md", "size": "1.2 KB", "mtime": "2026-01-01 12:05"},
        ]
        self.file_tree.populate(sample_files, "/home/omarchyvm")
        self.nav_path.setText("/home/omarchyvm")

    def _on_upload(self):
        """Handle file upload."""
        path, _ = QFileDialog.getOpenFileName(self, "Upload File to Guest", "", "All Files (*)")
        if path:
            self.terminal.append_line(f"Uploading: {path}...", "COMMAND")
            # Simulate upload
            QTimer.singleShot(1000, lambda: self.terminal.append_line(f"Upload complete: {path} → /home/omarchyvm/", "OUTPUT"))

    def _on_file_select(self, path: str):
        """Handle file double-click in tree."""
        if path.endswith("/"):
            self.nav_path.setText(path.rstrip("/"))
            self._refresh_files()
        else:
            self.terminal.append_line(f"Selected: {path}", "OUTPUT")
            self.terminal.append_line("Use Download button to retrieve this file.", "INFO")


# Keep the original GuestTerminalPanel class name for compatibility
GuestTerminalPanel = GuestTerminalPanel

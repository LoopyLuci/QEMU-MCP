"""Shared UI components for the QEMU-MCP GUI.

Reusable widgets: status indicator, icon button, labeled input field,
log entry widget, telemetry chart widget, credential tree item.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon, QPainter, QPalette, QFont, QFontMetrics
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QScrollArea,
    QGroupBox,
    QTabWidget,
    QMessageBox,
    QColorDialog,
    QFileDialog,
    QInputDialog,
    QComboBox,
)

from typing import Optional, List, Dict, Any


# ── Status Indicator ────────────────────────────────────────────────────────────

class StatusIndicator(QWidget):
    """Colored dot that shows connection/VM status."""

    color_changed = pyqtSignal(QColor)

    def __init__(self, color: QColor = QColor("#555555"), parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(12, 12)
        self.setCursor(Qt.PointingHandCursor)

    def set_status(self, running: bool, connected: bool = False):
        if running and connected:
            self._color = QColor("#22c55e")  # green
        elif running:
            self._color = QColor("#eab308")  # yellow
        elif connected:
            self._color = QColor("#3b82f6")  # blue
        else:
            self._color = QColor("#555555")  # gray
        self.update()
        self.color_changed.emit(self._color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(0, 0, self.width() - 1, self.height() - 1)

    def sizeHint(self) -> QSize:
        return QSize(12, 12)


# ── Icon Button ─────────────────────────────────────────────────────────────────

class IconButton(QPushButton):
    """Push button with icon and optional text."""

    def __init__(self, icon_path: Optional[str] = None, text: str = "", parent=None):
        super().__init__(parent)
        self._icon_path = icon_path
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            IconButton {
                border: 1px solid #334155;
                border-radius: 6px;
                background: #1e293b;
                color: #e2e8f0;
                padding: 8px 14px;
                font-size: 13px;
                min-height: 36px;
            }
            IconButton:hover {
                background: #334155;
                border-color: #475569;
            }
            IconButton:pressed {
                background: #475569;
            }
            IconButton:disabled {
                background: #1e293b;
                color: #64748b;
                border-color: #334155;
            }
            IconButton:checked {
                background: #3b82f6;
                border-color: #60a5fa;
                color: white;
            }
        """)

    def set_icon(self, icon: QIcon):
        self.setIcon(icon)
        self.setIconSize(QSize(20, 20))

    def sizeHint(self) -> QSize:
        sz = super().sizeHint()
        return QSize(max(sz.width(), 100), max(sz.height(), 36))


# ── Card Widget ─────────────────────────────────────────────────────────────────

class Card(QFrame):
    """A rounded card container for grouping related content."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet("""
            Card {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        if title:
            self.title_label = QLabel(title)
            self.title_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
            layout.addWidget(self.title_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(8)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.content_layout)

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_widgets(self, *widgets: QWidget):
        for w in widgets:
            self.content_layout.addWidget(w)

    def add_row(self, label: str, widget: QWidget, tooltip: str = ""):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        lbl.setFixedWidth(120)
        if tooltip:
            lbl.setToolTip(tooltip)
        row_layout.addWidget(lbl)

        widget.setStyleSheet("color: #e2e8f0; background: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px;")
        row_layout.addWidget(widget)
        row_layout.addStretch()
        self.content_layout.addWidget(row)


# ── Text Input Field ────────────────────────────────────────────────────────────

class TextInput(QLineEdit):
    """Styled text input."""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet("""
            TextInput {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 4px;
                color: #e2e8f0;
                padding: 6px 10px;
                font-size: 13px;
            }
            TextInput:focus {
                border-color: #3b82f6;
                background: #1e293b;
            }
        """)


# ── Password Input ──────────────────────────────────────────────────────────────

class PasswordInput(QWidget):
    """Password field with show/hide toggle."""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self._input = QLineEdit(self)
        self._input.setPlaceholderText(placeholder)
        self._input.setEchoMode(QLineEdit.Password)
        self._input.setStyleSheet("""
            QLineEdit {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 4px;
                color: #e2e8f0;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)

        self._toggle = QPushButton("👁", self)
        self._toggle.setFixedSize(28, 28)
        self._toggle.setCursor(Qt.PointingHandCursor)
        self._toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #e2e8f0;
            }
        """)
        self._toggle.clicked.connect(self._toggle_visibility)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._input)
        layout.addWidget(self._toggle)

    def _toggle_visibility(self):
        if self._input.echoMode() == QLineEdit.Password:
            self._input.setEchoMode(QLineEdit.Normal)
            self._toggle.setText("🙈")
        else:
            self._input.setEchoMode(QLineEdit.Password)
            self._toggle.setText("👁")

    def text(self) -> str:
        return self._input.text()

    def setText(self, text: str):
        self._input.setText(text)

    def setPlaceholderText(self, text: str):
        self._input.setPlaceholderText(text)

    def setFocus(self, focus: bool = True):
        if focus:
            self._input.setFocus()


# ── Log Entry Widget ────────────────────────────────────────────────────────────

class LogEntry(QFrame):
    """A single log entry row."""

    def __init__(self, timestamp: str, level: str, message: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setStyleSheet("""
            LogEntry {
                background: transparent;
                border: none;
            }
        """)

        levels = {
            "DEBUG": "#64748b",
            "INFO": "#38bdf8",
            "WARNING": "#f59e0b",
            "ERROR": "#ef4444",
            "CRITICAL": "#dc2626",
        }
        color = levels.get(level.upper(), "#94a3b8")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        ts_label = QLabel(timestamp)
        ts_label.setStyleSheet(f"color: {color}; font-size: 11px; font-family: monospace;")
        ts_label.setFixedWidth(80)
        layout.addWidget(ts_label)

        level_label = QLabel(level)
        level_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
        level_label.setFixedWidth(60)
        layout.addWidget(level_label)

        msg_label = QLabel(message)
        msg_label.setStyleSheet("color: #e2e8f0; font-size: 12px; font-family: monospace;")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        layout.addStretch()


# ── Telemetry Chart ─────────────────────────────────────────────────────────────

class TelemetryChart(QWidget):
    """Real-time line chart using matplotlib, embedded in PyQt5."""

    def __init__(self, title: str = "", value_label: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._value_label = value_label
        self._data: List[float] = []
        self._max_points = 60
        self._color = "#3b82f6"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.figure = __import__("matplotlib.figure").figure.Figure(figsize=(4, 2.5), dpi=100)
        self.canvas = __import__("matplotlib.backends.backend_qtagg", fromlist=["FigureCanvasQTAgg"]).FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)

        self._ax = self.figure.add_subplot(111)
        self._ax.set_facecolor("#0f172a")
        self._ax.set_title(title, color="#94a3b8", fontsize=10, pad=8)
        self._ax.tick_params(colors="#94a3b8", labelsize=8)
        self._ax.spines["bottom"].set_color("#334155")
        self._ax.spines["left"].set_color("#334155")
        self._ax.spines["top"].set_visible(False)
        self._ax.spines["right"].set_visible(False)
        self._ax.set_ylabel(value_label, color="#94a3b8", fontsize=8)
        self._ax.grid(True, alpha=0.2, color="#334155")
        self._line, = self._ax.plot([], [], color=self._color, linewidth=1.5)
        self._ax.set_xlim(0, self._max_points)
        self._ax.set_ylim(0, 100)

        self.setLayout(layout)

    def update_data(self, value: float):
        self._data.append(value)
        if len(self._data) > self._max_points:
            self._data = self._data[-self._max_points:]
        xs = list(range(len(self._data)))
        self._line.set_data(xs, self._data)
        if len(self._data) > 1:
            self._ax.set_xlim(0, len(self._data) - 1)
            self._ax.set_ylim(min(self._data) * 0.8, max(self._data) * 1.1)
        self.canvas.draw_idle()

    def clear(self):
        self._data = []
        self._line.set_data([], [])
        self.canvas.draw_idle()

    def set_color(self, color: str):
        self._color = color
        self._line.set_color(color)
        self.canvas.draw_idle()


# ── Credential Tree Item ────────────────────────────────────────────────────────

class CredentialTreeItem(QTreeWidgetItem):
    """A tree item representing a stored credential."""

    TYPE_COLORS = {
        "password": "#f59e0b",
        "ssh_key": "#8b5cf6",
        "api_key": "#22c55e",
        "qmp_pass": "#3b82f6",
        "other": "#94a3b8",
    }

    def __init__(self, cred_id: str, name: str, cred_type: str, description: str = "", parent=None):
        super().__init__(parent)
        self.cred_id = cred_id
        self.setText(0, name)
        color = self.TYPE_COLORS.get(cred_type, "#94a3b8")
        self.setText(1, cred_type)
        self.setText(2, description[:50] or "—")
        # Set color dot prefix in type column
        self.setIcon(1, __import__("PyQt5.QtGui", fromlist=["QIcon"]).QIcon())


# ── File Browser Tree ───────────────────────────────────────────────────────────

class FileTree(QTreeWidget):
    """Simple file browser tree for the guest filesystem."""

    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Name", "Size", "Modified"])
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.setAnimated(True)
        self.setRootIsDecorated(True)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTreeWidget {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 3px 4px;
            }
            QTreeWidget::item:selected {
                background: #3b82f6;
                color: white;
            }
            QTreeWidget::item:hover {
                background: #1e293b;
            }
            QHeaderView::section {
                background: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                padding: 4px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.itemDoubleClicked.connect(self._on_double_click)

    def _on_double_click(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, Qt.UserRole)
        if path:
            self.file_selected.emit(path)

    def populate(self, files: List[Dict[str, Any]], root_path: str = "/"):
        self.clear()
        root = QTreeWidgetItem(self, [root_path, "", ""])
        root.setData(0, Qt.UserRole, root_path)
        root.setExpanded(True)
        for f in files:
            child = QTreeWidgetItem(root, [f["name"], f"{f['size']}", f.get("mtime", "")])
            child.setData(0, Qt.UserRole, f.get("path", f"{root_path}/{f['name']}"))
            if f["type"] == "dir":
                child.setIcon(0, __import__("PyQt5.QtGui", fromlist=["QIcon"]).QIcon())
                child.setFlags(child.flags() | Qt.ItemIsAutoTristate)
            else:
                child.setIcon(0, __import__("PyQt5.QtGui", fromlist=["QIcon"]).QIcon())
        self.addTopLevelItem(root)
        self.expandAll()


# ── Terminal Output Widget ──────────────────────────────────────────────────────

class TerminalOutput(QPlainTextEdit):
    """Read-only terminal output with monospace font."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                padding: 8px;
            }
            QPlainTextEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self._timestamp_format = "%H:%M:%S"

    def append_line(self, text: str, level: str = "INFO"):
        from datetime import datetime
        ts = datetime.now().strftime(self._timestamp_format)
        colors = {
            "INFO": "#e2e8f0",
            "ERROR": "#ef4444",
            "WARNING": "#f59e0b",
            "COMMAND": "#38bdf8",
            "OUTPUT": "#a78bfa",
        }
        color = colors.get(level, "#e2e8f0")
        # Use setHtml for colored output
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.appendHtml(f'<span style="color:{color}">[{ts}] {escaped}</span>')

    def append_command(self, command: str):
        self.append_line(command, "COMMAND")

    def append_output(self, output: str):
        for line in output.split("\n"):
            if line.strip():
                self.append_line(line, "OUTPUT")

    def clear_terminal(self):
        self.clear()

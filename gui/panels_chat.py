"""Agentic Chat Panel — built-in LLM chat with QEMU tool execution."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QTextCursor, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QLineEdit, QComboBox, QSplitter, QFrame, QScrollArea, QSizePolicy,
    QProgressBar, QGroupBox, QGridLayout, QCheckBox, QSpinBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QInputDialog,
)

from gui.api_providers import APIProviders
from gui.chat_engine import ChatEngine, ChatMessage
from gui.provider_store import ProviderStore


class ChatPanel(QWidget):
    """Built-in agentic chat panel with QEMU tool execution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = ProviderStore()
        self._providers = APIProviders(self._store)
        self._engine = ChatEngine(self._providers)
        self._current_response = ""
        self._is_streaming = False
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Agentic Chat")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        self._provider_combo = QComboBox()
        self._provider_combo.setFixedWidth(150)
        self._provider_combo.setStyleSheet(
            "QComboBox { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px; }"
        )
        self._refresh_providers()
        hl.addWidget(QLabel("Provider:"))
        hl.addWidget(self._provider_combo)
        layout.addWidget(header)

        # Splitter for chat and usage
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # Chat display area
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setFont(QFont("Consolas", 10))
        self._chat_display.setStyleSheet(
            "QTextEdit { background: #0d1117; color: #c9d1d9;"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px; }"
        )
        splitter.addWidget(self._chat_display)

        # Input area
        input_row = QWidget()
        il = QHBoxLayout(input_row)
        il.setContentsMargins(0, 0, 0, 0)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask me anything about your VM...")
        self._input.returnPressed.connect(self._send_message)
        self._input.setStyleSheet(
            "QLineEdit { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px; }"
        )
        il.addWidget(self._input)

        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedSize(80, 36)
        self._send_btn.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
            "QPushButton:disabled { background: #334155; color: " + T.TEXT_MUTED + "; }"
        )
        self._send_btn.clicked.connect(self._send_message)
        il.addWidget(self._send_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedSize(70, 36)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: " + T.BG_SECONDARY + "; border: 1px solid " + T.BG_TERTIARY + ";"
            " border-radius: 6px; color: " + T.TEXT_SECONDARY + "; font-size: 12px; }"
            "QPushButton:hover { background: " + T.BG_TERTIARY + "; }"
        )
        self._clear_btn.clicked.connect(self._clear_history)
        il.addWidget(self._clear_btn)

        layout.addWidget(input_row)

        # Welcome message
        self._append_message("system", "Welcome to Agentic Chat! I can help you control your VM, execute commands, manage snapshots, and more.")
        self._append_message("system", "Select a provider above and start chatting. If you haven't configured an API key, go to Settings > AI Providers.")

    def _refresh_providers(self):
        """Refresh the provider dropdown."""
        self._provider_combo.clear()
        providers = self._store.get_enabled_providers()
        for p in providers:
            self._provider_combo.addItem(p.name)
        if not providers:
            self._provider_combo.addItem("No providers configured")

    def _send_message(self):
        """Send user message to the chat engine."""
        text = self._input.text().strip()
        if not text or self._is_streaming:
            return

        self._input.clear()
        self._is_streaming = True
        self._send_btn.setEnabled(False)
        self._current_response = ""

        # Display user message
        self._append_message("user", text)

        # Get selected provider
        provider_name = self._provider_combo.currentText()
        if provider_name == "No providers configured":
            self._append_message("system", "Error: No API providers configured. Please add an API key in Settings > AI Providers.")
            self._is_streaming = False
            self._send_btn.setEnabled(True)
            return

        # Run async chat
        self._run_chat(text, provider_name)

    def _run_chat(self, text: str, provider: str):
        """Run chat in async event loop."""
        loop = asyncio.new_event_loop()

        async def _chat():
            async for msg in self._engine.send_message(text):
                if msg.role == "assistant":
                    # Stream tokens would go here
                    pass
                elif msg.role == "tool":
                    self._append_message("tool", f"Executing {msg.tool_name}...")

        try:
            loop.run_until_complete(self._engine.send_message(text))
        except Exception as e:
            self._append_message("system", f"Error: {e}")
        finally:
            loop.close()
            self._is_streaming = False
            self._send_btn.setEnabled(True)

    def _append_message(self, role: str, content: str):
        """Append a message to the chat display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        colors = {
            "user": T.BRAND,
            "assistant": T.SUCCESS,
            "tool": T.WARNING,
            "system": T.TEXT_MUTED,
        }
        color = colors.get(role, T.TEXT_PRIMARY)
        
        role_labels = {
            "user": "You",
            "assistant": "AI",
            "tool": "Tool",
            "system": "System",
        }
        role_label = role_labels.get(role, role)
        
        html = f'<p><span style="color: {color}; font-weight: bold;">[{timestamp}] {role_label}:</span> {content}</p>'
        self._chat_display.append(html)
        
        # Auto-scroll
        self._chat_display.moveCursor(QTextCursor.End)

    def _clear_history(self):
        """Clear chat history."""
        self._chat_display.clear()
        self._engine.clear_history()
        self._append_message("system", "Chat history cleared.")

"""Example panel plugin for VM-Harness.

Demonstrates how to create a PanelPlugin that provides a custom GUI panel.
Drop this file into the plugins/ directory and it will be auto-discovered
by PluginManager.

To test: ensure PluginManager.load_all() is called during app startup,
then the panel will appear in the sidebar as "Example Panel".
"""

from __future__ import annotations

import asyncio

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QFrame,
)

from gui.plugin import PanelPlugin, PluginMetadata, PluginContext
from gui.theme import T


class ExamplePanelPlugin(PanelPlugin):
    """Example plugin that creates a simple informational panel."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="example-panel",
            version="1.0.0",
            description="Example panel plugin demonstrating the plugin API",
            author="VM-Harness Team",
            category="panel",
        )

    async def initialize(self, context: PluginContext) -> None:
        """Store the context for later use."""
        self._context = context
        self._click_count = 0

    async def shutdown(self) -> None:
        """Clean up resources."""
        pass

    def create_panel(self, parent) -> QWidget:
        """Create and return the example panel widget."""
        return ExamplePanel(parent)


class ExamplePanel(QWidget):
    """A simple example panel with a label and button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plugin: ExamplePanelPlugin | None = None
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Example Plugin Panel")
        title.setStyleSheet(
            "color: " + T.TEXT_PRIMARY + ";"
            "font-size: 20px; font-weight: bold;"
        )
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "This panel was loaded via the plugin system.\n"
            "It demonstrates how third-party plugins can extend VM-Harness."
        )
        desc.setStyleSheet(
            "color: " + T.TEXT_SECONDARY + "; font-size: 14px;"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: " + T.BG_TERTIARY + ";")
        layout.addWidget(line)

        # Interactive button
        btn_row = QHBoxLayout()
        self._btn = QPushButton("Click me!")
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet(
            "QPushButton {"
            "  background: " + T.BRAND + ";"
            "  color: white;"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 8px 16px;"
            "  font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "  background: " + T.BRAND_HOVER + ";"
            "}"
        )
        self._btn.clicked.connect(self._on_click)
        btn_row.addWidget(self._btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Click counter
        self._counter_label = QLabel("Clicks: 0")
        self._counter_label.setStyleSheet(
            "color: " + T.TEXT_MUTED + "; font-size: 13px;"
        )
        layout.addWidget(self._counter_label)

        layout.addStretch()

    def set_plugin(self, plugin: ExamplePanelPlugin) -> None:
        """Back-reference to the owning plugin instance."""
        self._plugin = plugin

    def _on_click(self) -> None:
        if self._plugin is not None:
            self._plugin._click_count += 1
            self._counter_label.setText(f"Clicks: {self._plugin._click_count}")

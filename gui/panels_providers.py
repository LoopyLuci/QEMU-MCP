"""AI Providers Settings Panel — configure API keys and models."""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout, QFrame,
    QSizePolicy, QMessageBox, QInputDialog,
)

from gui.provider_store import ProviderStore, ProviderConfig


class AIProvidersPanel(QWidget):
    """Configure AI provider API keys and models."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = ProviderStore()
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("AI Provider Configuration")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(80, 28)
        refresh_btn.setStyleSheet("background: " + T.BRAND + "; border: none; border-radius: 4px; color: white; font-size: 11px;")
        refresh_btn.clicked.connect(self.refresh)
        hl.addWidget(refresh_btn)
        layout.addWidget(header)

        # Provider table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Provider", "Model", "API Key", "Enabled", "Priority"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        layout.addWidget(self._table)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)

        add_key_btn = QPushButton("Set API Key")
        add_key_btn.setFixedSize(100, 32)
        add_key_btn.setStyleSheet("background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        add_key_btn.clicked.connect(self._set_api_key)
        bl.addWidget(add_key_btn)

        add_provider_btn = QPushButton("Add Custom")
        add_provider_btn.setFixedSize(100, 32)
        add_provider_btn.setStyleSheet("background: " + T.BG_SECONDARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        add_provider_btn.clicked.connect(self._add_custom_provider)
        bl.addWidget(add_provider_btn)

        bl.addStretch()
        layout.addWidget(btn_row)

        # Usage summary
        usage_group = QGroupBox("Usage Summary")
        usage_group.setStyleSheet("QGroupBox { color: " + T.TEXT_SECONDARY + "; font-size: 12px; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; margin-top: 8px; }")
        usage_layout = QGridLayout(usage_group)
        self._usage_label = QLabel("No usage data yet.")
        self._usage_label.setStyleSheet("color: " + T.TEXT_MUTED + "; font-size: 11px;")
        usage_layout.addWidget(self._usage_label, 0, 0)
        layout.addWidget(usage_group)

        self.refresh()

    def refresh(self):
        """Refresh the provider table."""
        providers = self._store.get_all_providers()
        self._table.setRowCount(len(providers))
        
        for i, (name, config) in enumerate(providers.items()):
            self._table.setItem(i, 0, QTableWidgetItem(name))
            self._table.setItem(i, 1, QTableWidgetItem(config.model))
            
            # Mask API key
            key_display = "••••••••" if config.api_key else "Not set"
            self._table.setItem(i, 2, QTableWidgetItem(key_display))
            
            enabled_item = QTableWidgetItem("Yes" if config.enabled else "No")
            self._table.setItem(i, 3, enabled_item)
            
            self._table.setItem(i, 4, QTableWidgetItem(str(config.priority)))

        # Update usage summary
        summary = self._store.get_usage_summary()
        if summary["total_requests"] > 0:
            self._usage_label.setText(
                f"Requests: {summary['total_requests']} | "
                f"Cost: ${summary['total_cost']:.4f} | "
                f"Tokens: {summary['total_tokens']:,} | "
                f"Success: {summary['success_rate']*100:.0f}%"
            )

    def _set_api_key(self):
        """Set API key for selected provider."""
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Select a provider first")
            return
        
        provider_name = self._table.item(row, 0).text()
        
        key, ok = QInputDialog.getText(
            self, "Set API Key",
            f"Enter API key for {provider_name}:",
            QLineEdit.Password,
        )
        
        if ok and key.strip():
            self._store.set_api_key(provider_name, key.strip())
            self.refresh()
            QMessageBox.information(self, "Success", f"API key for {provider_name} saved.")

    def _add_custom_provider(self):
        """Add a custom provider."""
        name, ok = QInputDialog.getText(self, "Add Provider", "Provider name:")
        if not ok or not name.strip():
            return
        
        base_url, ok = QInputDialog.getText(self, "Add Provider", "Base URL (e.g., https://api.example.com/v1):")
        if not ok:
            return
        
        model, ok = QInputDialog.getText(self, "Add Provider", "Model name:")
        if not ok:
            return
        
        api_key, ok = QInputDialog.getText(self, "Add Provider", "API key:", QLineEdit.Password)
        
        config = ProviderConfig(
            name=name.strip(),
            api_key=api_key or "",
            base_url=base_url.strip(),
            model=model.strip(),
        )
        self._store.add_provider(config)
        self.refresh()

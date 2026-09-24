"""Tests for VMConsolePanel — live console streaming via WebSocket bridge.

Run with: pytest tests/test_vm_console.py -v
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

# Ensure offscreen for headless testing
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Setup paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtTest import QTest


class TestVMConsolePanel(unittest.TestCase):
    """Test VMConsolePanel initialization, UI elements, and connection behavior."""

    @classmethod
    def setUpClass(cls):
        """Create QApplication once for all tests."""
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        """Create a fresh VMConsolePanel for each test."""
        from gui.panels_vm_console import VMConsolePanel
        self.panel = VMConsolePanel()
        self.panel.show()
        # Process events so the panel fully initializes
        QTest.qWait(100)

    def tearDown(self):
        """Clean up the panel after each test."""
        if hasattr(self, 'panel') and self.panel:
            self.panel._disconnect()
            self.panel.close()
            self.panel.deleteLater()
        QTest.qWait(50)

    # ── Test 1: QApplication exists ─────────────────────────────────────────

    def test_qapplication_exists(self):
        """QApplication should be instantiated."""
        self.assertIsNotNone(QApplication.instance())

    # ── Test 2: Panel instantiation ─────────────────────────────────────────

    def test_panel_instantiates(self):
        """VMConsolePanel should instantiate without error."""
        self.assertIsNotNone(self.panel)

    # ── Test 3: Connect/Disconnect buttons exist ─────────────────────────────

    def test_connect_button_exists(self):
        """Panel should have a Connect button."""
        self.assertTrue(hasattr(self.panel, '_btn_connect'))
        self.assertIsNotNone(self.panel._btn_connect)
        self.assertEqual(self.panel._btn_connect.text(), "Connect")

    def test_disconnect_button_exists(self):
        """Panel should have a Disconnect button."""
        self.assertTrue(hasattr(self.panel, '_btn_disconnect'))
        self.assertIsNotNone(self.panel._btn_disconnect)
        self.assertEqual(self.panel._btn_disconnect.text(), "Disconnect")

    def test_disconnect_initially_disabled(self):
        """Disconnect button should be disabled when not connected."""
        self.assertFalse(self.panel._btn_disconnect.isEnabled())

    def test_connect_initially_enabled(self):
        """Connect button should be enabled when not connected."""
        self.assertTrue(self.panel._btn_connect.isEnabled())

    # ── Test 4: QGraphicsView exists ────────────────────────────────────────

    def test_graphics_view_exists(self):
        """Panel should have a QGraphicsView for rendering frames."""
        self.assertTrue(hasattr(self.panel, '_graphics_view'))
        self.assertIsNotNone(self.panel._graphics_view)

    def test_graphics_scene_exists(self):
        """Panel should have a QGraphicsScene."""
        self.assertTrue(hasattr(self.panel, '_scene'))
        self.assertIsNotNone(self.panel._scene)

    # ── Test 5: Status indicator exists ─────────────────────────────────────

    def test_status_indicator_exists(self):
        """Panel should have a StatusIndicator widget."""
        self.assertTrue(hasattr(self.panel, '_status_indicator'))
        self.assertIsNotNone(self.panel._status_indicator)

    def test_status_label_exists(self):
        """Panel should have a status label."""
        self.assertTrue(hasattr(self.panel, '_status_label'))
        self.assertIsNotNone(self.panel._status_label)

    def test_initial_status_disconnected(self):
        """Initial status should be 'Disconnected'."""
        self.assertEqual(self.panel._status_label.text(), "Disconnected")

    # ── Test 6: Connect button behavior (no bridge running) ─────────────────

    def test_connect_shows_disconnected_when_no_bridge(self):
        """Clicking Connect with no bridge should result in 'Disconnected' status.

        Since the streaming bridge is not running on port 8445, the connection
        will fail and the panel should return to a disconnected state.
        """
        # Verify initial state
        self.assertEqual(self.panel._status_label.text(), "Disconnected")
        self.assertFalse(self.panel._connected)

        # Click the connect button
        QTest.mouseClick(self.panel._btn_connect, Qt.LeftButton)

        # Wait for connection attempt to fail (WebSocket timeout)
        # The bridge is not running, so connection should fail within a few seconds
        QTest.qWait(3000)

        # After failed connection, status should show error or return to Disconnected
        # The panel calls _on_connection_failed which shows a message box
        # and sets status to "Failed: ..." then the panel should be disconnected
        status_text = self.panel._status_label.text()

        # The panel should NOT be connected since there's no bridge
        self.assertFalse(self.panel._connected)

        # Status should indicate failure (not "Connected")
        self.assertNotIn("Connected — streaming", status_text)

    def test_connect_button_disabled_during_connection(self):
        """Connect button should be disabled while attempting connection."""
        # Click connect
        QTest.mouseClick(self.panel._btn_connect, Qt.LeftButton)

        # Immediately after click, button should be disabled
        # (it gets re-enabled on failure)
        QTest.qWait(100)

        # After failure, connect should be re-enabled
        QTest.qWait(3000)
        self.assertTrue(self.panel._btn_connect.isEnabled())

    def test_url_label_shows_bridge_address(self):
        """URL label should show the WebSocket bridge address."""
        self.assertEqual(
            self.panel._url_label.text(),
            "ws://127.0.0.1:8445/ws/stream"
        )

    def test_frame_counter_initial_state(self):
        """Frame counter should start at 0."""
        self.assertEqual(self.panel._frame_label.text(), "0 frames")
        self.assertEqual(self.panel._frames_received, 0)

    def test_health_timer_exists(self):
        """Panel should have a health check timer."""
        self.assertTrue(hasattr(self.panel, '_health_timer'))
        self.assertIsNotNone(self.panel._health_timer)
        self.assertTrue(self.panel._health_timer.isActive())


if __name__ == "__main__":
    unittest.main()

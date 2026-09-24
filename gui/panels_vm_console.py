"""VM Console Streaming Panel — live console via Continuum Streaming Bridge.

Connects to ws://127.0.0.1:8445/ws/stream and renders binary JPEG frames
in a QGraphicsView.  Provides connect/disconnect, connection status, and
manual refresh controls.
"""

from __future__ import annotations

from typing import Any

import json
import threading
import time
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt5.QtGui import QColor, QImage, QPixmap, QPainter, QFont, QIcon, QKeyEvent
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFrame,
    QSizePolicy, QMessageBox,
)

from gui.theme import T
from gui.widgets import Card, StatusIndicator


class VMConsolePanel(QWidget):
    """Live VM console streaming via WebSocket → QGraphicsView.

    Protocol (from streaming_bridge.py):
      - Client connects to ws://127.0.0.1:8445/ws/stream
      - Server pushes binary JPEG frames continuously
      - Client may send JSON: {"type":"config","quality":85,...}
      - Client may send JSON: {"type":"ping","time":<ms>}
      - Client may send JSON: {"type":"input","input_type":...}
      - Client may send JSON: {"type":"stats_request"}
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── State ──────────────────────────────────────────────────────────
        self._ws = None                     # websocket.WebSocketApp | None
        self._ws_thread: Optional[object] = None   # threading.Thread
        self._connected = False
        self._last_frame_time: float = 0.0
        self._frames_received: int = 0
        self._bytes_received: int = 0
        self._frame_width: int = 0
        self._frame_height: int = 0

        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)

        # ── Header ────────────────────────────────────────────────────────
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)

        title = QLabel("VM Console")
        title.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: 16px; font-weight: bold;"
        )
        hl.addWidget(title)
        hl.addStretch()

        # Frame counter
        self._frame_label = QLabel("0 frames")
        self._frame_label.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: 11px;"
        )
        hl.addWidget(self._frame_label)

        layout.addWidget(header)

        # ── Connection Controls Card ─────────────────────────────────────
        ctrl_card = Card("Connection")
        ctrl_card.setFixedHeight(56)
        layout.addWidget(ctrl_card)

        ctrl_row = QWidget()
        crl = QHBoxLayout(ctrl_row)
        crl.setContentsMargins(0, 0, 0, 0)
        crl.setSpacing(10)

        self._status_indicator = StatusIndicator(QColor(T.DOT_OFFLINE))
        crl.addWidget(self._status_indicator, alignment=Qt.AlignVCenter)

        self._status_label = QLabel("Disconnected")
        self._status_label.setStyleSheet(
            f"color: {T.STATUS_STOPPED}; font-size: 12px;"
        )
        crl.addWidget(self._status_label)

        self._url_label = QLabel("ws://127.0.0.1:8445/ws/stream")
        self._url_label.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: 11px;"
            f"font-family: Consolas, monospace;"
        )
        crl.addWidget(self._url_label)

        crl.addStretch()

        # Connect button
        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setFixedHeight(32)
        self._btn_connect.setCursor(Qt.PointingHandCursor)
        self._btn_connect.setStyleSheet(
            f"QPushButton {{ background: {T.BRAND}; color: white; border: none;"
            f" border-radius: 6px; font-size: 12px; font-weight: 600;"
            f" padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {T.BRAND_HOVER}; }}"
            f"QPushButton:disabled {{ background: {T.BRAND}20; color: {T.TEXT_MUTED}; }}"
        )
        self._btn_connect.clicked.connect(self._connect)
        crl.addWidget(self._btn_connect)

        # Disconnect button
        self._btn_disconnect = QPushButton("Disconnect")
        self._btn_disconnect.setFixedHeight(32)
        self._btn_disconnect.setCursor(Qt.PointingHandCursor)
        self._btn_disconnect.setEnabled(False)
        self._btn_disconnect.setStyleSheet(
            f"QPushButton {{ background: {T.ERROR}; color: white; border: none;"
            f" border-radius: 6px; font-size: 12px; font-weight: 600;"
            f" padding: 0 16px; }}"
            f"QPushButton:hover {{ background: #dc2626; }}"
            f"QPushButton:disabled {{ background: {T.ERROR_BG}; color: {T.TEXT_MUTED}; }}"
        )
        self._btn_disconnect.clicked.connect(self._disconnect)
        crl.addWidget(self._btn_disconnect)

        # Refresh button — forces a config re-request / reconnection ping
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.setFixedHeight(32)
        self._btn_refresh.setCursor(Qt.PointingHandCursor)
        self._btn_refresh.setEnabled(False)
        self._btn_refresh.setToolTip("Request a fresh config/frame from the bridge")
        self._btn_refresh.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {T.TEXT_SECONDARY};"
            f" border: 1px solid {T.BG_TERTIARY}; border-radius: 6px;"
            f" font-size: 12px; padding: 0 14px; }}"
            f"QPushButton:hover {{ color: {T.TEXT_PRIMARY}; border-color: {T.BRAND}; }}"
            f"QPushButton:disabled {{ color: {T.TEXT_MUTED}; border-color: {T.BG_TERTIARY}; }}"
        )
        self._btn_refresh.clicked.connect(self._refresh)
        crl.addWidget(self._btn_refresh)

        ctrl_card.content_layout.addWidget(ctrl_row)

        # ── Streaming Display (QGraphicsView) ─────────────────────────────
        display_card = Card("Console Output")
        layout.addWidget(display_card, stretch=1)

        self._scene = QGraphicsScene(self)
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._placeholder_text = None

        self._graphics_view = QGraphicsView(self._scene)
        self._graphics_view.setRenderHints(
            QPainter.SmoothPixmapTransform
            | QPainter.Antialiasing
        )
        self._graphics_view.setFrameShape(QFrame.NoFrame)
        self._graphics_view.setStyleSheet(
            f"QGraphicsView {{"
            f"  background: {T.BG_SECONDARY};"
            f"  border: 1px solid {T.BG_TERTIARY};"
            f"  border-radius: 6px;"
            f"}}"
        )
        self._graphics_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._graphics_view.setMinimumHeight(300)
        self._graphics_view.setAlignment(Qt.AlignCenter)
        self._graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)

        # Placeholder text when not connected
        self._set_placeholder("Disconnected — press Connect to start streaming")

        display_card.content_layout.addWidget(self._graphics_view, stretch=1)

        # ── Status Bar (bottom info) ─────────────────────────────────────
        status_row = QWidget()
        srl = QHBoxLayout(status_row)
        srl.setContentsMargins(0, 0, 0, 0)
        srl.setSpacing(16)

        self._res_label = QLabel("—")
        self._res_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
        srl.addWidget(self._res_label)

        self._fps_label = QLabel("—")
        self._fps_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
        srl.addWidget(self._fps_label)

        self._bytes_label = QLabel("—")
        self._bytes_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
        srl.addWidget(self._bytes_label)

        srl.addStretch()

        self._time_label = QLabel("")
        self._time_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
        srl.addWidget(self._time_label)

        layout.addWidget(status_row)

        # ── Auto-reconnect timer (monitors connection health) ─────────────
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(5000)
        self._health_timer.timeout.connect(self._check_health)
        self._health_timer.start()

    # ── Connection Management ──────────────────────────────────────────────

    def _connect(self):
        """Connect to the streaming bridge WebSocket."""
        if self._connected:
            return

        try:
            import websocket
        except ImportError:
            QMessageBox.critical(
                self, "Dependency Missing",
                "websocket-client is required for VM console streaming.\n"
                "Install it with: pip install websocket-client",
            )
            return

        self._btn_connect.setEnabled(False)
        self._btn_connect.setText("Connecting…")
        self._status_label.setText("Connecting…")
        self._status_label.setStyleSheet(
            f"color: {T.WARNING}; font-size: 12px;"
        )

        ws_url = "ws://127.0.0.1:8445/ws/stream"

        try:
            self._ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
            )
            self._ws_thread = threading.Thread(
                target=self._ws.run_forever,
                kwargs={"ping_interval": 30, "ping_timeout": 10},
                daemon=True,
            )
            self._ws_thread.start()
        except Exception as exc:
            self._on_connection_failed(str(exc))

    def _disconnect(self):
        """Disconnect from the streaming bridge."""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self._connected = False
        self._ws = None
        self._ws_thread = None
        self._update_disconnected_state()

    def _refresh(self):
        """Request fresh config and trigger a new frame burst."""
        if not self._connected or not self._ws:
            return

        # Send a config request with current settings — bridge will respond
        # with config_ack and continue sending frames immediately.
        try:
            self._ws.send(json.dumps({
                "type": "config",
                "quality": 85,
                "fps": 60,
            }))
            # Also send a ping to force an immediate response
            self._ws.send(json.dumps({
                "type": "ping",
                "time": int(time.time() * 1000),
            }))
        except Exception as exc:
            self._status_label.setText(f"Refresh failed: {exc}")
            self._status_label.setStyleSheet(
                f"color: {T.ERROR}; font-size: 12px;"
            )

    # ── WebSocket Callbacks (called from WS thread) ───────────────────────

    def _on_ws_open(self, ws):
        """WebSocket connection opened."""
        # Schedule UI updates on the main thread via QTimer.singleShot
        from PyQt5.QtCore import QTimer as _QT
        _QT.singleShot(0, self._handle_connected)

    def _on_ws_message(self, ws, message):
        """Handle incoming WebSocket message (binary frame or JSON text)."""
        if isinstance(message, (bytes, bytearray)):
            # Binary — JPEG frame
            self._handle_frame(bytes(message))
        else:
            # Text — JSON control message
            self._handle_control_message(message)

    def _on_ws_error(self, ws, error):
        """WebSocket error occurred."""
        from PyQt5.QtCore import QTimer as _QT
        _QT.singleShot(0, lambda: self._handle_ws_error(str(error)))

    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed."""
        from PyQt5.QtCore import QTimer as _QT
        _QT.singleShot(0, lambda: self._handle_disconnected())

    # ── Frame Rendering ────────────────────────────────────────────────────

    def _handle_frame(self, data: bytes):
        """Decode a JPEG frame and render it in the QGraphicsView."""
        try:
            image = QImage.fromData(data, "JPEG")
            if image.isNull():
                return

            pixmap = QPixmap.fromImage(image)
            self._frame_width = pixmap.width()
            self._frame_height = pixmap.height()
            self._frames_received += 1
            self._bytes_received += len(data)
            self._last_frame_time = time.time()

            # Update scene on main thread
            from PyQt5.QtCore import QTimer as _QT
            _QT.singleShot(0, lambda: self._update_pixmap(pixmap))
        except Exception:
            pass

    def _update_pixmap(self, pixmap: QPixmap):
        """Update the QGraphicsView with a new frame (main thread only)."""
        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
        else:
            self._pixmap_item.setPixmap(pixmap)

        # Remove placeholder if present
        if self._placeholder_text is not None:
            self._scene.removeItem(self._placeholder_text)
            self._placeholder_text = None

        # Scale view to fit while preserving aspect ratio
        self._graphics_view.fitInView(
            self._pixmap_item, Qt.KeepAspectRatio
        )

        # Update stats
        self._frame_label.setText(f"{self._frames_received} frames")
        self._res_label.setText(f"{self._frame_width}×{self._frame_height}")
        mb = self._bytes_received / (1024 * 1024)
        self._bytes_label.setText(f"{mb:.1f} MB received")

    def _handle_control_message(self, raw: str):
        """Parse JSON control messages from the bridge."""
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return

        msg_type = msg.get("type", "")

        if msg_type == "config_ack":
            # Bridge acknowledged config — update status
            pass
        elif msg_type == "pong":
            pass
        elif msg_type == "stats":
            frames_sent = msg.get("frames_sent", 0)
            # Could show bridge-side stats in status bar

    # ── State Update Helpers (main thread) ────────────────────────────────

    def _handle_connected(self):
        """Update UI when WebSocket connects (main thread)."""
        self._connected = True
        self._frames_received = 0
        self._bytes_received = 0

        self._status_indicator.set_status(running=True, connected=True)
        self._status_label.setText("Connected — streaming")
        self._status_label.setStyleSheet(
            f"color: {T.STATUS_RUNNING}; font-size: 12px;"
        )

        self._btn_connect.setEnabled(False)
        self._btn_connect.setText("Connected")
        self._btn_disconnect.setEnabled(True)
        self._btn_refresh.setEnabled(True)

        self._set_placeholder("Waiting for frames…")

    def _handle_disconnected(self):
        """Update UI when WebSocket closes (main thread)."""
        self._connected = False
        self._update_disconnected_state()

    def _handle_ws_error(self, message: str):
        """Update UI on WebSocket error (main thread)."""
        self._connected = False
        self._status_label.setText(f"Error: {message[:60]}")
        self._status_label.setStyleSheet(
            f"color: {T.ERROR}; font-size: 12px;"
        )
        self._btn_connect.setEnabled(True)
        self._btn_connect.setText("Connect")
        self._btn_disconnect.setEnabled(False)
        self._btn_refresh.setEnabled(False)

    def _on_connection_failed(self, message: str):
        """Handle initial connection failure."""
        self._btn_connect.setEnabled(True)
        self._btn_connect.setText("Connect")
        self._status_label.setText(f"Failed: {message[:60]}")
        self._status_label.setStyleSheet(
            f"color: {T.ERROR}; font-size: 12px;"
        )
        QMessageBox.critical(
            self, "Connection Failed",
            f"Could not connect to streaming bridge:\n{message}\n\n"
            "Make sure streaming_bridge.py is running on port 8445.",
        )

    def _update_disconnected_state(self):
        """Reset UI to disconnected state."""
        self._status_indicator.set_status(running=False, connected=False)
        self._status_label.setText("Disconnected")
        self._status_label.setStyleSheet(
            f"color: {T.STATUS_STOPPED}; font-size: 12px;"
        )

        self._btn_connect.setEnabled(True)
        self._btn_connect.setText("Connect")
        self._btn_disconnect.setEnabled(False)
        self._btn_refresh.setEnabled(False)

        self._set_placeholder("Disconnected — press Connect to start streaming")

    def _set_placeholder(self, text: str):
        """Show centered placeholder text in the graphics view."""
        # Clear existing items
        self._scene.clear()
        self._pixmap_item = None

        # Add new placeholder
        from PyQt5.QtGui import QFont as _QF
        self._placeholder_text = self._scene.addText(
            text,
            _QF("Segoe UI", 13),
        )
        self._placeholder_text.setDefaultTextColor(QColor(T.TEXT_MUTED))
        self._placeholder_text.setPos(20, 20)

    def _check_health(self):
        """Periodic health check — detect stale connections."""
        if not self._connected:
            return

        # If no frame received in 15 seconds, connection is likely stale
        if self._last_frame_time > 0:
            elapsed = time.time() - self._last_frame_time
            if elapsed > 15:
                self._status_label.setText("Stale — reconnecting…")
                self._status_label.setStyleSheet(
                    f"color: {T.WARNING}; font-size: 12px;"
                )
                self._disconnect()

    def closeEvent(self, event: Any) -> None:
        """Clean up WebSocket on panel close."""
        self._disconnect()
        super().closeEvent(event)


# Ensure threading is available for type hints
import threading  # noqa: E402

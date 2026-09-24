"""Continuum Streaming Bridge — bridges Continuum's QUIC protocol to WebSocket for Android.

Run: python streaming_bridge.py
Captures desktop frames via Continuum's native capture, encodes them,
and streams to Android clients over WebSocket with input event forwarding.
"""

from __future__ import annotations

import asyncio
import base64
import ctypes
import json
import logging
import os
import queue
import struct
import subprocess
import sys
import threading
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable

import aiohttp
from aiohttp import web, WSMessage
import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

log = logging.getLogger("continuum.bridge")


# ── Configuration ─────────────────────────────────────────────────────────────

CONTINUUM_SERVER = "127.0.0.1:4433"
BRIDGE_WS_PORT = 8445
BRIDGE_WS_HOST = "0.0.0.0"
CAPTURE_FPS = 60
DEFAULT_QUALITY = 85
MAX_WIDTH = 1920
MAX_HEIGHT = 1080

# ── Docker exec subprocess pool ───────────────────────────────────────────────

class DockerExecSession:
    """Manages a docker exec subprocess for terminal access."""

    def __init__(self, container_name: str, shell: str = "/bin/sh"):
        self.container_name = container_name
        self.shell = shell
        self.process: Optional[subprocess.Popen] = None
        self.output_callbacks: List[Callable] = []
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._output_queue: queue.Queue = queue.Queue()

    def start(self):
        """Start docker exec subprocess."""
        try:
            self.process = subprocess.Popen(
                ["docker", "exec", "-it", self.container_name, self.shell],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                universal_newlines=True,
            )
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()
        except Exception as e:
            log.error(f"Failed to start docker exec for {self.container_name}: {e}")

    def _read_output(self):
        """Read output from subprocess."""
        if not self.process or not self.process.stdout:
            return
        while self._running and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    self._output_queue.put(line)
                    for cb in self.output_callbacks:
                        cb(line)
            except Exception:
                break

    def write(self, data: str):
        """Write to subprocess stdin."""
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(data + "\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def resize(self, cols: int, rows: int):
        """Resize terminal (Unix only)."""
        if self.process and self.process.stdin:
            try:
                import fcntl, termios, struct
                fcntl.ioctl(self.process.stdin.fileno(), termios.TIOCSWINSZ,
                           struct.pack("HHHH", rows, cols, 0, 0))
            except Exception:
                pass

    def get_output(self, timeout: float = 0.1) -> Optional[str]:
        """Get output from queue (non-blocking)."""
        try:
            return self._output_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        """Stop subprocess."""
        self._running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()


class ExecSessionManager:
    """Manages multiple docker exec sessions."""

    def __init__(self):
        self._sessions: Dict[str, DockerExecSession] = {}

    def get_or_create(self, container_name: str) -> DockerExecSession:
        """Get existing session or create new one."""
        if container_name not in self._sessions:
            session = DockerExecSession(container_name)
            session.start()
            self._sessions[container_name] = session
        return self._sessions[container_name]

    def close(self, container_name: str):
        """Close a session."""
        if container_name in self._sessions:
            self._sessions[container_name].stop()
            del self._sessions[container_name]

    def close_all(self):
        """Close all sessions."""
        for name in list(self._sessions.keys()):
            self.close(name)


# Global exec session manager
exec_sessions = ExecSessionManager()


# ── Frame Capture ─────────────────────────────────────────────────────────────

@dataclass
class MonitorInfo:
    id: int
    name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool = True


class FrameCapture:
    """Captures frames from the desktop using Continuum's capture backend.
    
    Falls back to screenshots crate equivalent on Windows.
    """
    
    def __init__(self, monitor_id: int = 0):
        self.monitor_id = monitor_id
        self._capturing = False
        self._last_frame: Optional[bytes] = None
        self._frame_lock = threading.Lock()
        self._capture_thread: Optional[threading.Thread] = None
        self._fps = CAPTURE_FPS
        self._quality = DEFAULT_QUALITY
        self._width = MAX_WIDTH
        self._height = MAX_HEIGHT
        
    def start(self):
        """Start continuous frame capture."""
        self._capturing = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        
    def stop(self):
        """Stop frame capture."""
        self._capturing = False
        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)
    
    def set_fps(self, fps: int):
        self._fps = max(1, min(120, fps))
    
    def set_quality(self, quality: int):
        self._quality = max(10, min(100, quality))
    
    def set_resolution(self, width: int, height: int):
        self._width = width
        self._height = height
    
    def _capture_loop(self):
        """Continuous capture loop running in background thread."""
        import ctypes
        import ctypes.wintypes
        
        # Use Windows GDI for screen capture
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        
        while self._capturing:
            try:
                frame = self._capture_frame_gdi(user32, gdi32)
                if frame:
                    with self._frame_lock:
                        self._last_frame = frame
            except Exception as e:
                log.error(f"Capture error: {e}")
            
            time.sleep(1.0 / self._fps)
    
    def _capture_frame_gdi(self, user32, gdi32) -> Optional[bytes]:
        """Capture a frame using Windows GDI."""
        try:
            # Get screen dimensions
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            
            # Create compatible DC and bitmap
            hwnd = user32.GetDesktopWindow()
            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            
            # StretchBlt to scale down if needed
            dest_width = min(self._width, screen_width)
            dest_height = min(self._height, screen_height)
            
            hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, dest_width, dest_height)
            gdi32.SelectObject(hdc_mem, hbitmap)
            
            # Copy screen (with stretching)
            gdi32.StretchBlt(
                hdc_mem, 0, 0, dest_width, dest_height,
                hdc_screen, 0, 0, screen_width, screen_height,
                0x00CC0020  # SRCCOPY
            )
            # Get bitmap bits
            bmp_info = ctypes.create_string_buffer(40)
            ctypes.memmove(bmp_info, bytes([
                40, 0, 0, 0,  # biSize
                dest_width & 0xFF, (dest_width >> 8) & 0xFF, 0, 0,  # biWidth
                dest_height & 0xFF, (dest_height >> 8) & 0xFF, 0, 0,  # biHeight
                1, 0,  # biPlanes
                32, 0,  # biBitCount
                0, 0, 0, 0,  # biCompression
            ] + [0] * 20), 40)
            
            # Actually use a simpler approach with PIL if available
            if HAS_PIL:
                # Use PIL's ImageGrab for reliable capture
                from PIL import ImageGrab
                img = ImageGrab.grab(bbox=(0, 0, screen_width, screen_height))
                img = img.resize((dest_width, dest_height), Image.LANCZOS)
                
                # Encode to JPEG
                import io
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=self._quality, optimize=True)
                result = buf.getvalue()
            else:
                # Fallback: use screenshots crate via subprocess
                result = self._capture_via_subprocess(dest_width, dest_height)
            
            # Cleanup
            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            
            return result
            
        except Exception as e:
            log.error(f"GDI capture error: {e}")
            return None
    
    def _capture_via_subprocess(self, width: int, height: int) -> Optional[bytes]:
        """Fallback capture using Python screenshots library."""
        try:
            import subprocess
            result = subprocess.run([
                sys.executable, "-c",
                f"""
import sys
try:
    from PIL import ImageGrab, Image
    import io
    img = ImageGrab.grab()
    img = img.resize(({width}, {height}), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality={self._quality})
    sys.stdout.buffer.write(buf.getvalue())
except Exception as e:
    sys.stderr.write(str(e))
"""
            ], capture_output=True, timeout=2)
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except:
            pass
        return None
    
    def get_frame(self) -> Optional[bytes]:
        """Get the latest captured frame."""
        with self._frame_lock:
            return self._last_frame


# ── Input Injection ───────────────────────────────────────────────────────────

class InputInjector:
    """Injects input events into the local desktop."""
    
    def __init__(self):
        self._enigo = None
        try:
            import enigo
            self._enigo = enigo.Enigo()
        except ImportError:
            log.warning("enigo not available, using ctypes fallback")
    
    def mouse_move(self, x: int, y: int):
        """Move mouse to absolute position."""
        if self._enigo:
            self._enigo.move_mouse(x, y, enigo.Coords.Absolute)
        else:
            import ctypes
            ctypes.windll.user32.SetCursorPos(x, y)
    
    def mouse_relative(self, dx: int, dy: int):
        """Move mouse relative to current position."""
        if self._enigo:
            self._enigo.move_mouse(dx, dy, enigo.Coords.Relative)
        else:
            import ctypes
            ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)
    
    def mouse_click(self, button: str, pressed: bool):
        """Send mouse click."""
        if self._enigo:
            btn = {"left": enigo.Button.Left, "right": enigo.Button.Right, "middle": enigo.Button.Middle}.get(button, enigo.Button.Left)
            if pressed:
                self._enigo.mouse_down(btn)
            else:
                self._enigo.mouse_up(btn)
        else:
            import ctypes
            flag_down = {"left": 0x0002, "right": 0x0008, "middle": 0x0020}
            flag_up = {"left": 0x0004, "right": 0x0010, "middle": 0x0040}
            if pressed:
                ctypes.windll.user32.mouse_event(flag_down.get(button, 0x0002), 0, 0, 0, 0)
            else:
                ctypes.windll.user32.mouse_event(flag_up.get(button, 0x0004), 0, 0, 0, 0)
    
    def scroll(self, dx: int, dy: int):
        """Send scroll event."""
        if self._enigo:
            self._enigo.scroll(dx, dy)
        else:
            import ctypes
            if dy != 0:
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, dy * 120, 0)
            if dx != 0:
                ctypes.windll.user32.mouse_event(0x1000, 0, 0, dx * 120, 0)
    
    def key(self, key_code: int, pressed: bool):
        """Send key event."""
        if self._enigo:
            # Map key codes to enigo keys
            pass
        else:
            import ctypes
            if pressed:
                ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)
            else:
                ctypes.windll.user32.keybd_event(key_code, 0, 2, 0)


# ── WebSocket Server ──────────────────────────────────────────────────────────

@dataclass
class ClientSession:
    """An active streaming client session."""
    ws: web.WebSocketResponse
    client_id: str
    quality: int = DEFAULT_QUALITY
    fps: int = CAPTURE_FPS
    width: int = MAX_WIDTH
    height: int = MAX_HEIGHT
    monitor_id: int = 0
    input_enabled: bool = True
    last_frame_sent: float = 0.0
    bytes_sent: int = 0
    frames_sent: int = 0


class StreamingBridge:
    """Main streaming bridge server."""
    
    def __init__(self):
        self.capture = FrameCapture()
        self.input_injector = InputInjector()
        self.clients: Dict[str, ClientSession] = {}
        self._app: Optional[web.Application] = None
        self._running = False
        
    async def start(self):
        """Start the streaming bridge."""
        self.capture.start()
        
        self._app = web.Application()
        self._app.router.add_get("/ws/stream", self._handle_ws)
        self._app.router.add_get("/terminal/{container}", self._handle_terminal_ws)
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/monitors", self._handle_monitors)
        self._app.router.add_post("/config", self._handle_config)
        
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, BRIDGE_WS_HOST, BRIDGE_WS_PORT)
        await site.start()
        
        log.info(f"Streaming bridge listening on ws://{BRIDGE_WS_HOST}:{BRIDGE_WS_PORT}")
        self._running = True
        
        # Start frame broadcaster
        asyncio.create_task(self._broadcast_loop())
        
        # Keep running
        while self._running:
            await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the streaming bridge."""
        self._running = False
        self.capture.stop()
        for client in list(self.clients.values()):
            await client.ws.close()
    
    async def _handle_terminal_ws(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket endpoint for Docker container terminal access.

        Clients send JSON: {"command": "ls"}
        Server responds: {"output": "file1 file2..."}
        """
        container_name = request.match_info.get("container", "")
        if not container_name:
            return web.Response(status=400, text="Missing container name")

        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        log.info(f"Terminal WebSocket connected for container: {container_name}")

        # Get or create exec session
        session = exec_sessions.get_or_create(container_name)

        # Poll queue and send output to WebSocket
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        command = data.get("command", "")
                        if command:
                            session.write(command)
                    except json.JSONDecodeError:
                        pass
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.error(f"Terminal WebSocket error: {ws.exception()}")
                    break

                # Poll for output (non-blocking)
                while True:
                    output = session.get_output(timeout=0.05)
                    if output is None:
                        break
                    try:
                        await ws.send_str(json.dumps({"output": output}))
                    except Exception:
                        break
        finally:
            log.info(f"Terminal WebSocket disconnected for container: {container_name}")

        return ws

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection from Android client."""
        ws = web.WebSocketResponse(
            heartbeat=30.0,
            autoping=True,
            max_msg_size=10 * 1024 * 1024,
        )
        await ws.prepare(request)
        
        client_id = request.query.get("client_id", f"client_{id(ws)}")
        session = ClientSession(ws=ws, client_id=client_id)
        self.clients[client_id] = session
        
        log.info(f"Client connected: {client_id}")
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(session, msg.data)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    pass
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.error(f"WS error: {ws.exception()}")
        except Exception as e:
            log.error(f"Client error: {e}")
        finally:
            del self.clients[client_id]
            log.info(f"Client disconnected: {client_id}")
        
        return ws
    
    async def _handle_message(self, session: ClientSession, data: str):
        """Handle incoming message from client."""
        try:
            msg = json.loads(data)
            msg_type = msg.get("type")
            
            if msg_type == "config":
                # Client configuration
                if "quality" in msg:
                    session.quality = max(10, min(100, msg["quality"]))
                    self.capture.set_quality(session.quality)
                if "fps" in msg:
                    session.fps = max(1, min(120, msg["fps"]))
                    self.capture.set_fps(session.fps)
                if "width" in msg and "height" in msg:
                    session.width = msg["width"]
                    session.height = msg["height"]
                    self.capture.set_resolution(session.width, session.height)
                if "monitor_id" in msg:
                    session.monitor_id = msg["monitor_id"]
                    self.capture.monitor_id = session.monitor_id
                if "input_enabled" in msg:
                    session.input_enabled = msg["input_enabled"]
                
                await session.ws.send_json({
                    "type": "config_ack",
                    "quality": session.quality,
                    "fps": session.fps,
                    "width": session.width,
                    "height": session.height,
                })
            
            elif msg_type == "input":
                # Input event from client
                if session.input_enabled:
                    await self._handle_input(msg)
            
            elif msg_type == "ping":
                await session.ws.send_json({"type": "pong", "time": msg.get("time", 0)})
            
            elif msg_type == "stats_request":
                await session.ws.send_json({
                    "type": "stats",
                    "bytes_sent": session.bytes_sent,
                    "frames_sent": session.frames_sent,
                    "clients": len(self.clients),
                })
                
        except json.JSONDecodeError:
            log.warning(f"Invalid JSON from client: {data[:100]}")
    
    async def _handle_input(self, msg: dict):
        """Handle input event."""
        input_type = msg.get("input_type")
        
        if input_type == "mouse_move":
            x = msg.get("x", 0)
            y = msg.get("y", 0)
            relative = msg.get("relative", False)
            if relative:
                self.input_injector.mouse_relative(int(x), int(y))
            else:
                self.input_injector.mouse_move(int(x), int(y))
        
        elif input_type == "mouse_click":
            button = msg.get("button", "left")
            pressed = msg.get("pressed", True)
            self.input_injector.mouse_click(button, pressed)
        
        elif input_type == "scroll":
            dx = msg.get("dx", 0)
            dy = msg.get("dy", 0)
            self.input_injector.scroll(int(dx), int(dy))
        
        elif input_type == "key":
            key_code = msg.get("key_code", 0)
            pressed = msg.get("pressed", True)
            self.input_injector.key(key_code, pressed)
    
    async def _broadcast_loop(self):
        """Broadcast frames to all connected clients."""
        while self._running:
            try:
                frame = self.capture.get_frame()
                if frame:
                    # Send to all clients
                    disconnected = []
                    for client_id, session in self.clients.items():
                        try:
                            # Send frame as binary
                            await session.ws.send_bytes(frame)
                            session.frames_sent += 1
                            session.bytes_sent += len(frame)
                            session.last_frame_sent = time.time()
                        except Exception:
                            disconnected.append(client_id)
                    
                    # Clean up disconnected clients
                    for client_id in disconnected:
                        if client_id in self.clients:
                            del self.clients[client_id]
                
                # Adaptive sleep based on client FPS
                if self.clients:
                    min_fps = min(s.fps for s in self.clients.values())
                    await asyncio.sleep(1.0 / min_fps)
                else:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                log.error(f"Broadcast error: {e}")
                await asyncio.sleep(0.1)
    
    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "ok",
            "clients": len(self.clients),
            "capturing": self.capture._capturing,
        })
    
    async def _handle_monitors(self, request: web.Request) -> web.Response:
        """List available monitors."""
        monitors = self._enumerate_monitors()
        return web.json_response({"monitors": monitors})
    
    async def _handle_config(self, request: web.Request) -> web.Response:
        """Update bridge configuration."""
        body = await request.json()
        if "quality" in body:
            self.capture.set_quality(body["quality"])
        if "fps" in body:
            self.capture.set_fps(body["fps"])
        return web.json_response({"status": "ok"})
    
    def _enumerate_monitors(self) -> List[dict]:
        """Enumerate available monitors."""
        try:
            if HAS_PIL:
                from PIL import ImageGrab
                # PIL doesn't directly enumerate monitors, use screen size
                import ctypes
                user32 = ctypes.windll.user32
                width = user32.GetSystemMetrics(0)
                height = user32.GetSystemMetrics(1)
                return [{
                    "id": 0,
                    "name": "Primary Display",
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": height,
                    "is_primary": True,
                }]
        except:
            pass
        return [{
            "id": 0,
            "name": "Default Display",
            "x": 0,
            "y": 0,
            "width": 1920,
            "height": 1080,
            "is_primary": True,
        }]


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    bridge = StreamingBridge()
    
    try:
        await bridge.start()
    except KeyboardInterrupt:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())

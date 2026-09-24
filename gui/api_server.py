"""REST API Server — programmatic access to all VM-Harness operations."""

from __future__ import annotations

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("qemu-mcp.api")

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from vm_harness.config import VmMCPSettings, Secrets
from vm_harness.setup import QMPClient


class QMCPAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for VM-Harness REST API."""

    def _send_json(self, data: Any, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _send_error(self, message: str, status: int = 400):
        """Send error response."""
        self._send_json({"error": message}, status)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        # API routes
        routes = {
            "/api/v1/status": self._get_status,
            "/api/v1/vms": self._list_vms,
            "/api/v1/config": self._get_config,
            "/api/v1/isos": self._list_isos,
        }

        handler = routes.get(path, self._not_found)
        handler(params)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        routes = {
            "/api/v1/vm/start": self._start_vm,
            "/api/v1/vm/stop": self._stop_vm,
            "/api/v1/vm/restart": self._restart_vm,
            "/api/v1/vm/snapshot/create": self._create_snapshot,
        }

        handler = routes.get(path, self._not_found)
        handler()

    def do_DELETE(self):
        """Handle DELETE requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/v1/vm/snapshot":
            self._delete_snapshot()
        else:
            self._not_found({})

    def _get_status(self, params: dict):
        """Get overall system status."""
        settings = VmMCPSettings()
        status = {
            "server": "qemu-mcp",
            "version": "1.0.0",
            "qmp_host": settings.qmp_host,
            "qmp_port": settings.qmp_port,
            "vm_name": settings.vm_name,
            "vm_disk_path": str(settings.vm_disk_path) if settings.vm_disk_path else None,
        }
        self._send_json(status)

    def _list_vms(self, params: dict):
        """List all configured VMs."""
        vms = []
        # Add the default VM
        settings = VmMCPSettings()
        vms.append({
            "name": settings.vm_name,
            "disk_path": str(settings.vm_disk_path) if settings.vm_disk_path else None,
            "qmp_port": settings.qmp_port,
        })
        self._send_json({"vms": vms})

    def _get_config(self, params: dict):
        """Get current configuration."""
        settings = VmMCPSettings()
        config = {
            "qmp_host": settings.qmp_host,
            "qmp_port": settings.qmp_port,
            "vm_name": settings.vm_name,
            "vm_ram_mb": settings.vm_ram_mb,
            "vm_cpus": settings.vm_cpus,
            "vm_display": settings.vm_display,
        }
        self._send_json(config)

    def _list_isos(self, params: dict):
        """List available ISOs."""
        sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

        from gui.iso_manager import ISOManager
        manager = ISOManager()
        isos = manager.scan_isos()
        self._send_json({"isos": isos})

    def _start_vm(self):
        """Start a VM."""
        self._send_json({"status": "not_implemented", "message": "Use QMP bridge for VM control"})

    def _stop_vm(self):
        """Stop a VM."""
        self._send_json({"status": "not_implemented", "message": "Use QMP bridge for VM control"})

    def _restart_vm(self):
        """Restart a VM."""
        self._send_json({"status": "not_implemented", "message": "Use QMP bridge for VM control"})

    def _create_snapshot(self):
        """Create a VM snapshot."""
        self._send_json({"status": "not_implemented", "message": "Use qemu-img for snapshots"})

    def _delete_snapshot(self):
        """Delete a VM snapshot."""
        self._send_json({"status": "not_implemented", "message": "Use qemu-img for snapshots"})

    def _not_found(self, params: dict):
        """Handle unknown routes."""
        self._send_error("Not found", 404)


class QMCPAPIServer:
    """REST API server for VM-Harness."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self._host = host
        self._port = port
        self._server: Optional[HTTPServer] = None

    def start(self):
        """Start the API server."""
        self._server = HTTPServer((self._host, self._port), QMCPAPIHandler)
        logger.info("API server started on %s:%d", self._host, self._port)
        self._server.serve_forever()

    def stop(self):
        """Stop the API server."""
        if self._server:
            self._server.shutdown()
            logger.info("API server stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = QMCPAPIServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()

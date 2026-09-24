# VM-Harness Android Companion App — Comprehensive Design Document

**Version:** 1.0-draft  
**Status:** Design proposal  
**Target:** Kotlin + Jetpack Compose Android app with full feature parity to the desktop Python/PyQt5 GUI, remote access via Tailscale mesh networking + API key pairing (QR code + manual entry).

---

## 1. Architecture Overview

### 1.1 Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                     Tailscale Mesh Network                   │
│  (encrypted WireGuard tunnels, MagicDNS, 100.x.y.z IPs)    │
│                                                             │
│   ┌──────────────────┐         ┌──────────────────────┐    │
│   │  Android Device  │         │   Desktop Host        │    │
│   │                  │         │                      │    │
│   │ ┌─────────────┐  │         │ ┌──────────────────┐ │    │
│   │ │ VM-Harness    │  │ HTTPS   │ │ VM-Harness Server │ │    │
│   │ │ Android App │◄─┼─────────┼─│ (local API +     │ │    │
│   │ │ (Kotlin/    │  │  WS     │ │  MCP tools)     │ │    │
│   │ │  Compose)   │  │         │ │                  │ │    │
│   │ └─────────────┘  │         │ │ ┌────────────┐  │ │    │
│   │                  │         │ │ │ QEMU mgr   │  │ │    │
│   │ ┌─────────────┐  │         │ │ │ + QMP/SSH │  │ │    │
│   │ │ Tailscale   │  │         │ │ └────────────┘  │ │    │
│   │ │ Android App │  │         │ └──────────────────┘ │    │
│   │ │ (VPN tunnel) │  │         │                      │    │
│   │ └─────────────┘  │         │ ┌──────────────────┐ │    │
│   └──────────────────┘         │ │ MCP Server      │ │    │
│                                 │ │ (tool endpoints)│ │    │
│                                 │ └──────────────────┘ │    │
│                                 └──────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

The Android app NEVER talks directly to QEMU. It talks to the **desktop app's local API server**, which in turn uses QMP/SSH/MCP. This means:

- The Android app is a **thin remote client** — no QEMU logic, no QMP protocol, no SSH key management.
- All VM operations go through the desktop app's existing bridges (`QMPBridge`, `SSHBridge`, `MultiVMQMPBridge`).
- The desktop app is the authority — it owns the credential store, audit log, settings, providers, chat engine, etc.
- The Android app renders the same capabilities through a mobile-idiomatic UI.

### 1.2 Desktop API Server (New Component)

The desktop app gains a lightweight local HTTP server (bound to the Tailscale interface, or all interfaces with Tailscale IP filtering) that exposes the same capabilities as the GUI. This server is **not** a separate process — it runs inside the existing VM-Harness Python process, sharing the same bridges, credential store, audit log, settings, and providers.

**Why inside the existing process (not a separate MCP server):**

- Zero duplication of credential_store, audit_log, settings, providers, chat_engine.
- The GUI and Android client share the exact same state.
- One process to authorize, audit, and update.
- The `--headless` mode already validates the full init path — the API server can run alongside the GUI, or the GUI can be replaced by the API server on headless hosts.

**Server framework:** `aiohttp` (already a dependency via `asyncssh`/`mcp` ecosystem) or `starlette` + `uvicorn`. Both are async, lightweight, and integrate cleanly with the existing asyncio event loop the GUI already runs.

### 1.3 Android App Architecture (Clean Architecture)

```
Android App
├── UI Layer (Jetpack Compose + ViewModel)
│   ├── Dashboard screen
│   ├── VM Control screen
│   ├── Guest Terminal screen (SSH over WebSocket)
│   ├── Telemetry screen (charts, alerts)
│   ├── Settings screen
│   ├── Security screen (credentials, audit log)
│   ├── Logs screen
│   ├── Multi-VM switcher
│   ├── Chat/Agent screen (if parity with desktop chat engine)
│   ├── Pairing/Welcome screen (QR scan, manual entry)
│   └── ISO Manager, USB config, QMP console (secondary screens)
│
├── Domain Layer (pure Kotlin, no Android deps)
│   ├── Models: VMStatus, TelemetryData, Credential, AuditEntry, QMPCommand, etc.
│   ├── Use cases: StartVM, StopVM, ResetVM, SendQMP, RunSSHCommand, etc.
│   └── Repository interfaces
│
├── Data Layer (Repository implementations)
│   ├── DesktopApiRepository — Retrofit/OkHttp + WebSocket for all desktop API calls
│   ├── PairingStore — EncryptedSharedPreferences / Android Keystore for paired device info
│   └── TelemetryCache — in-memory or Room for chart data (optional, mostly live stream)
│
└── Infrastructure
    ├── TailscaleResolver — uses MagicDNS / Tailscale IP to resolve the desktop hostname
    ├── AuthInterceptor — attaches API key to every request
    ├── WebSocketTerminal — SSH terminal over the desktop's WebSocket bridge
    └── QRScanner — ML Kit barcode scanning for pairing
```

---

## 2. Tailscale Integration

### 2.1 What Tailscale Provides

| Capability | How it's used |
|---|---|
| **Encrypted mesh network** | All Android↔Desktop traffic travels inside WireGuard tunnels — no open ports, no port forwarding, no firewall rules. |
| **MagicDNS** | Desktop is reachable by a stable hostname like `omnarchy-vm.tailnet-name.ts.net`. Android resolves it via DNS — no hardcoded IPs. |
| **100.x.y.z IPs** | Each node gets a stable IPv4 in the Tailscale range. The desktop API server binds to this IP (or 0.0.0.0 with a Tailscale IP allowlist). |
| **Node authentication** | Tailscale already authenticates nodes via TLS certs + user auth. The API key is an additional application-layer guard. |
| **Lax/dogfood/custom tailnets** | Works on personal tailnets, Teams, or Enterprise — no special config beyond the user being logged into Tailscale on both devices. |
| **Exit nodes / subnet routers** | If the desktop is a subnet router, the Android app can reach VMs directly too — but the Android app still goes through the desktop API for parity. |

### 2.2 Desktop Side: Tailscale Detection & Binding

The desktop API server needs to know which interface to bind to. On startup:

1. Query Tailscale's local API (`http://localhost:9000` or the `tailscale` CLI) to get:
   - The machine's Tailscale IP (e.g., `100.123.45.67`)
   - The MagicDNS name (e.g., `omnarchy-vm.tail123.ts.net`)
   - The tailnet name
   - Whether Tailscale is running
2. If Tailscale is active, bind the API server to the Tailscale IP (or `0.0.0.0` + filter by `100.0.0.0/8` source IPs).
3. If Tailscale is not active, the API server does NOT start — the Android app cannot connect. The GUI still works locally.

**Detecting Tailscale on Windows (desktop):**

```python
# Option A: tailscale CLI (most reliable)
import subprocess
result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True)
# Parse JSON for TailscaleIP, MagicDNSSuffix, etc.

# Option B: localhost API (requires tailscale to be running with API enabled)
import aiohttp
async with aiohttp.ClientSession() as session:
    async with session.get("http://localhost:9000/endpoint") as resp:
        ...
```

**Binding the server:**

```python
# Bind to Tailscale IP only — no localhost, no LAN exposure
api = web.Application()
# ... routes ...
runner = web.AppRunner(api)
await runner.setup()
site = web.TCPSite(runner, host=tailscale_ip, port=8443)
await site.start()
```

**Alternative: bind to 0.0.0.0 + source IP filtering.** This is simpler and works even if Tailscale's IP changes. Filter incoming connections to only `100.0.0.0/8` (Tailscale IPv4 range) plus the machine's own localhost for health checks.

### 2.3 Android Side: Tailscale Dependency

The Android app does NOT embed Tailscale. The user installs the official Tailscale Android app (from Google Play or F-Droid) on their device. When Tailscale is active on the Android device:

- The Android app's HTTP client can resolve MagicDNS names (e.g., `omnarchy-vm.tail123.ts.net`) and reach the desktop's Tailscale IP.
- All traffic is encrypted and authenticated at the network layer.

**Pre-requisite check in the Android app:**

On the welcome/pairing screen, the app checks:
1. Is Tailscale installed? (query PackageManager for `co.tailscale.tailscale` or the F-Droid package name)
2. Is Tailscale active? (check if the `cn.tailscale.tailscaled` VPN service is running, or try to resolve a known MagicDNS name)
3. If not, show a clear "Install Tailscale" prompt with Play Store / F-Droid links.

This is a soft requirement — the app can show a friendly error rather than crashing.

---

## 3. API Key Pairing System

### 3.1 Design Goals

- **Zero-config**: scan a QR code on the desktop screen, tap to pair.
- **Manual fallback**: type the key if QR isn't practical.
- **Baked-in network data**: the key encodes the Tailscale hostname, IP, machine fingerprint, timestamp, and purpose — so the Android app can validate it and auto-configure the connection.
- **Random secret**: the actual authorization token is a random high-entropy value, not derivable from the baked-in data.
- **One-time pairing**: once paired, the key is stored on the Android device and reused. No repeated QR scans.
- **Rotation**: the desktop can regenerate keys (e.g., after losing a device), and the Android app re-pairs.

### 3.2 Key Structure

The pairing key is a **signed, self-describing token** — not just a random string. It's a compact encoded blob that contains both the metadata (baked-in network/machine data) and the random secret, signed by the desktop so the Android app can verify authenticity.

**Format (conceptual):**

```
PairingToken = Base64URL( HMAC-SHA256( payload, desktop_secret ) + "." + payload )

payload = {
    "kid": "v1",                          # key format version
    "purpose": "mobile-pairing",         # what this key is for
    "host": "omnarchy-vm.tail123.ts.net", # MagicDNS name
    "ip": "100.123.45.67",               # Tailscale IP
    "tailnet": "tail123",                # tailnet name (for display/validation)
    "machine_id": "sha256:abc123...",   # machine fingerprint (hash of hostname+uuid+etc)
    "created": 1735689600,               # Unix timestamp
    "expires": 1735776000,               # optional expiry (e.g., 24h for QR, "perpetual" for manual)
    "secret": "random-256-bit-base64"    # the actual authorization secret
}
```

**Desktop secret:** A persistent key stored in the desktop's credential store (Fernet-encrypted, alongside the VM credentials). Used to sign pairing tokens. Never leaves the desktop.

**Why HMAC, not encryption:** The Android app doesn't need to decrypt the payload — it just needs to verify it came from the desktop. HMAC verification requires the desktop secret, which the Android app does NOT have (it only gets the signed token). Wait — that doesn't work for verification on the Android side.

**Better approach: RSA/ECDSA signature.**

The desktop has an asymmetric key pair:
- **Private key** (stored in credential store, Fernet-encrypted) — signs pairing tokens.
- **Public key** — baked into the Android app (or downloaded from the desktop on first connection). The Android app verifies signatures with the public key.

**Revised format:**

```
PairingToken = Base64URL( ECDSA_SHA256_signature ) + "." + Base64URL( payload )

payload = JSON({
    "kid": "v1",
    "purpose": "mobile-pairing",
    "host": "omnarchy-vm.tail123.ts.net",
    "ip": "100.123.45.67",
    "tailnet": "tail123",
    "machine_id": "sha256:abc123...",
    "created": 1735689600,
    "expires": 1735776000,   # or null for perpetual
    "secret": "random-256-bit-base64"
})
```

**Android verification flow:**
1. Parse the token: `signature.payload`.
2. Base64-decode payload, parse JSON.
3. Validate fields: `kid` is "v1", `purpose` is "mobile-pairing", `host` is a valid MagicDNS name, `ip` is in `100.0.0.0/8`, `created` is recent, `expires` is null or in the future.
4. Verify the signature against the desktop's public key (baked into the app).
5. If valid, store `secret` + `host` + `ip` + `tailnet` + `machine_id` in the PairingStore (Keystore-backed).
6. The `secret` is sent as the API key on every subsequent request.

### 3.3 QR Code Contents

The QR code encodes a **URI** that the Android app can parse:

```
vmharness://pair?
  host=omnarchy-vm.tail123.ts.net&
  ip=100.123.45.67&
  key=eyJ...ECDSA_signature.payload_base64...
```

Or a simpler form that embeds everything in the `key` parameter (the full signed token):

```
vmharness://pair?key=eyJ...signature...payload...
```

The Android app's URIs scheme `vmharness://pair` is registered so the Android OS can hand off the QR scan result directly to the app (deep linking). If the app isn't installed yet, the QR code also displays a human-readable fallback (the raw key string) for manual entry.

**QR code display on desktop (GUI + headless):**

- GUI: a dialog in Settings → "Pair Mobile Device" shows the QR code (generated via `qrcode` Python library) and the raw key string.
- Headless: the key + QR (as ASCII or saved to a file) is printed to stdout / saved to a config file.

### 3.4 Manual Entry

The desktop shows the raw key string in addition to the QR code:

```
vmharness://pair?key=eyJhbGciOi...long-base64-string...
```

Or a shortened form:

```
Pairing Key: a1b2c3d4-e5f6-7890-abcd-ef1234567890 (copy this)
Host: omnarchy-vm.tail123.ts.net
```

The Android app has a "Enter key manually" field where the user pastes the full URI or the key string. The app parses it, validates, and stores the pairing.

### 3.5 Pairing Flow (Step by Step)

**Desktop (initiate):**

1. User opens Settings → "Pair Mobile Device" (or runs `vmharness pair` in headless mode).
2. Desktop generates:
   - A random 256-bit secret (`secrets.token_bytes(32)`).
   - A payload with host, IP, tailnet, machine_id, timestamps.
   - Signs the payload with the desktop's ECDSA private key.
   - Encodes the token as `signature.payload` (Base64URL).
3. Desktop displays:
   - QR code (containing `vmharness://pair?key=...`).
   - Raw key string (for manual entry / copy-paste).
   - Hostname + IP for verification.
4. Desktop enters "pairing mode" — the API server accepts the pairing endpoint (`POST /api/v1/auth/pair`) which validates the incoming token against the desktop's public key and stores the secret as an authorized API key.

**Android (join):**

1. User opens the VM-Harness Android app → lands on Pairing screen (if not yet paired).
2. Option A — QR scan:
   - Tap "Scan QR" → ML Kit barcode scanner opens → camera frames → decodes QR → extracts `vmharness://pair?key=...` URI.
   - App parses the URI, extracts the token.
   - Validates signature against baked-in public key.
   - Validates payload fields (host, IP range, timestamps).
   - If valid, stores the pairing in PairingStore (Keystore) and proceeds to connection test.
3. Option B — Manual entry:
   - Tap "Enter key manually" → text field → paste the key string.
   - Same validation as QR path.
4. Connection test:
   - App resolves `host` via DNS (MagicDNS) → gets the Tailscale IP.
   - Sends `GET /api/v1/status?key=<secret>` to verify the desktop is reachable and the key works.
   - If successful → pairing complete, navigate to Dashboard.
   - If failed → show clear error ("Desktop not reachable. Is Tailscale running on both devices?") with retry.

**Re-pairing (key rotation):**

- Desktop: Settings → "Revoke Mobile Devices" → lists paired devices (by machine_id or hostname) → revoke one.
- Android: on next API call, gets 401 → prompts to re-pair (scan QR again or enter new key).

### 3.6 machine_id Computation

The `machine_id` is a stable fingerprint of the desktop machine, computed once and stored. It's used by the Android app to display "Connected to: Omnarchy Workstation" rather than a raw IP.

**Computation (desktop, at first run):**

```python
import hashlib, uuid, platform, os

def compute_machine_id() -> str:
    # Combine stable identifiers
    parts = [
        platform.node(),           # hostname
        str(uuid.getnode()),      # MAC address (stable per NIC)
        platform.machine(),       # e.g., "AMD64"
        platform.system(),        # e.g., "Windows"
    ]
    # Hash for privacy (don't expose raw hostname/MAC to the mobile app)
    raw = "|".join(parts).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:32]
```

Store in credential store (Fernet-encrypted). Display name (human-readable) is separate — from settings or hostname.

---

## 4. Desktop API Server — Endpoint Design

The API server exposes REST + WebSocket endpoints that mirror every desktop GUI capability. All endpoints (except `/api/v1/auth/pair` and `/api/v1/auth/verify`) require the API key in the `X-API-Key` header (or `?key=` query param for QR-initiated first contact).

### 4.1 Authentication & Pairing

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/pair` | Accept a pairing token, validate signature, store the secret as an authorized API key. Returns `{ paired: true, host, display_name }`. |
| `GET` | `/api/v1/auth/verify` | Verify the current API key is valid. Returns `{ valid: true, desktop_version, tailscale_ip, machine_id, display_name }`. |
| `POST` | `/api/v1/auth/revoke` | Revoke the current API key (call from Android to self-revoke, or from desktop to revoke a specific key by id). |

### 4.2 Dashboard & VM Lifecycle

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/` or `/api/v1/dashboard` | Dashboard summary: VM list with status, host metrics (CPU, RAM, disk), recent alerts, quick-stats. |
| `GET` | `/api/v1/vms` | List all VMs (name, status, QMP URI, SSH URI, RAM, vCPUs, disk, last started, uptime). |
| `GET` | `/api/v1/vms/{name}` | Single VM detail (full config, status, network interfaces, block devices, metadata). |
| `POST` | `/api/v1/vms/{name}/start` | Start VM (QMP `cont` or full power-on). |
| `POST` | `/api/v1/vms/{name}/stop` | Stop VM (graceful shutdown via QMP, or force). |
| `POST` | `/api/v1/vms/{name}/reset` | Reset VM (QMP `system_reset`). |
| `POST` | `/api/v1/vms/{name}/powerdown` | Power down (QMP `system_powerdown`). |
| `POST` | `/api/v1/vms/{name}/pause` | Pause (QMP `stop`). |
| `POST` | `/api/v1/vms/{name}/resume` | Resume (QMP `cont`). |
| `POST` | `/api/v1/vms/{name}/eject-cdrom` | Eject CDROM (QMP `eject`). |
| `POST` | `/api/v1/vms/{name}/inject-key` | Inject keyboard event (QMP `inject_key_event`). |
| `GET` | `/api/v1/vms/{name}/status` | Live status stream (pollable, or WebSocket for push). |

### 4.3 QMP Console

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/vms/{name}/qmp` | WebSocket — raw QMP command/response stream for the QMP console panel. |
| `POST` | `/api/v1/vms/{name}/qmp/command` | Send a single QMP command, return response (REST fallback for non-WebSocket clients). |

### 4.4 SSH / Guest Terminal

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/vms/{name}/terminal` | WebSocket — bidirectional SSH terminal stream (the desktop app's SSH bridge runs the SSH session; the WebSocket carries stdin/stdout/stderr). |
| `POST` | `/api/v1/vms/{name}/ssh/command` | Run a single SSH command, return stdout/stderr/exit_code (REST fallback). |
| `GET` | `/api/v1/vms/{name}/ssh/files/{path}` | List directory (REST). |
| `GET` | `/api/v1/vms/{name}/ssh/file/{path}` | Read file (REST, with size limit). |
| `POST` | `/api/v1/vms/{name}/ssh/file/{path}` | Write file (REST, with size limit). |
| `DELETE` | `/api/v1/vms/{name}/ssh/file/{path}` | Remove file (REST). |

### 4.5 Telemetry & Metrics

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/metrics` | Host metrics: CPU%, RAM used/total, disk usage per drive, network I/O. |
| `GET` | `/api/v1/metrics/vm/{name}` | VM metrics: vCPU usage, RAM, balloon, disk I/O, network I/O. |
| `GET` | `/api/v1/metrics/stream` | WebSocket — live metrics stream (push, every N seconds). |
| `GET` | `/api/v1/alerts` | Recent alerts (CPU threshold, disk low, VM crash, etc.). |
| `GET` | `/api/v1/alerts/stream` | WebSocket — live alerts push. |
| `GET` | `/api/v1/history` | Telemetry history (polled, paginated, time-range filtered). |

### 4.6 Settings & Configuration

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/settings` | All desktop settings (as JSON — mirrors `pydantic-settings` config). |
| `PUT` | `/api/v1/settings` | Update settings (partial patch). |
| `GET` | `/api/v1/providers` | AI provider configs (names, keys status, usage). |
| `GET` | `/api/v1/providers/{name}/usage` | Usage records for a provider. |

### 4.7 Security & Credentials

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/security/audit` | Audit log entries (paginated, filtered by time/action/user). |
| `GET` | `/api/v1/credentials` | Credential store listing (names, types, usage count — not the secrets). |
| `GET` | `/api/v1/credentials/{name}` | Credential detail (decrypted value — requires elevated auth; see §5). |
| `POST` | `/api/v1/credentials` | Add a credential (name, type, value). |
| `PUT` | `/api/v1/credentials/{name}` | Update a credential. |
| `DELETE` | `/api/v1/credentials/{name}` | Delete a credential. |

### 4.8 VM Management (Multi-VM)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/multi-vm` | Multi-VM state: active VM, mode (switch/concurrent), VM list. |
| `POST` | `/api/v1/multi-vm/switch/{name}` | Switch active VM. |
| `POST` | `/api/v1/multi-vm/mode/{mode}` | Set mode. |
| `POST` | `/api/v1/multi-vm/start-all` | Start all VMs. |
| `POST` | `/api/v1/multi-vm/stop-all` | Stop all VMs. |
| `POST` | `/api/v1/multi-vm/send/{command}` | Send QMP command to active VM. |

### 4.9 VM Cloning & Snapshots

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/vms/{name}/clone` | Clone a VM (source, new name, optional config overrides). |
| `GET` | `/api/v1/vms/{name}/snapshots` | List snapshots. |
| `POST` | `/api/v1/vms/{name}/snapshots` | Create snapshot. |
| `DELETE` | `/api/v1/vms/{name}/snapshots/{snapname}` | Delete snapshot. |
| `POST` | `/api/v1/vms/{name}/snapshots/{snapname}/restore` | Restore snapshot. |
| `GET` | `/api/v1/snapshot-schedules` | Snapshot schedules. |
| `POST` | `/api/v1/snapshot-schedules` | Create schedule. |
| `DELETE` | `/api/v1/snapshot-schedules/{id}` | Delete schedule. |

### 4.10 ISO Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/iso` | ISO library listing (path, size, VMs using it). |
| `POST` | `/api/v1/iso/add` | Add ISO path to library. |
| `DELETE` | `/api/v1/iso/{name}` | Remove ISO from library. |
| `GET` | `/api/v1/iso/{name}/contents` | ISO file listing (if readable). |

### 4.11 USB Passthrough Configuration

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/usb/devices` | List host USB devices available for passthrough. |
| `POST` | `/api/v1/vms/{name}/usb/attach` | Attach USB device to VM. |
| `DELETE` | `/api/v1/vms/{name}/usb/{id}` | Detach USB device from VM. |

### 4.12 Logs

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/logs` | Application logs (paginated, filtered by level/time). |
| `GET` | `/api/v1/logs/stream` | WebSocket — live log tail. |

### 4.13 Chat / Agent (if parity with desktop chat engine)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/chat` | Chat history. |
| `POST` | `/api/v1/chat/message` | Send a chat message, get streaming response (Server-Sent Events or WebSocket). |
| `GET` | `/api/v1/chat/tools` | List available MCP tools (for the agent). |

### 4.14 System Information

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/sysinfo` | Host system info (CPU, RAM, OS, QEMU version, disk, network). |

### 4.15 Monitoring & Troubleshooting

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/monitoring` | Monitoring dashboard data (alerts, metrics, events). |
| `GET` | `/api/v1/troubleshoot` | Troubleshooting diagnostics (QMP connection status, SSH status, Tailscale status, provider status). |

### 4.16 Network & Storage

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/network` | Network config (interfaces, routing, DNS, open ports). |
| `PUT` | `/api/v1/network` | Update network config. |
| `GET` | `/api/v1/storage` | Storage info (disk usage, VM disk sizes, paths). |

### 4.17 WebSocket Protocol Details

Several features need bidirectional, low-latency streaming — the guest terminal (SSH), QMP console, metrics, alerts, and logs. These use WebSocket endpoints.

**WebSocket message format (JSON):**

```json
// Client → Server (e.g., SSH stdin)
{ "type": "stdin", "data": "ls -la\n" }

// Server → Client (e.g., SSH stdout)
{ "type": "stdout", "data": "total 42\n..." }

// Server → Client (e.g., metrics push)
{ "type": "metric", "data": { "cpu": 42.3, "ram": 8.2, "ts": 1735689600 } }

// Server → Client (e.g., QMP response)
{ "type": "qmp-response", "data": { "return": {...}, "id": "cmd-1" } }
```

The desktop API server maintains a connection registry: each WebSocket connects with the API key (in the subprotocol or first message), and the server associates it with the authorized session.

### 4.18 API Key Transmission

- **REST:** `X-API-Key: <secret>` header (preferred) or `?key=<secret>` query param (for QR-initiated first contact where the URL is clicked/opened).
- **WebSocket:** The API key is sent as the first message after connect: `{ "type": "auth", "key": "<secret>" }`, or as a subprotocol `vmharness-api-key-<secret>` (less ideal — logs it). Use the first-message approach.

---

## 5. Security Model

### 5.1 Defense in Depth

| Layer | Mechanism | Notes |
|---|---|---|
| **Network** | Tailscale WireGuard tunnels | All traffic encrypted, authenticated at the node level. No open ports. Only Tailscale IPs can reach the API server. |
| **Application** | API key (random 256-bit secret) | Required on every request. Signed pairing token ensures the key came from the desktop. |
| **Desktop secret storage** | Fernet + PBKDF2 (existing credential_store) | The ECDSA signing key and paired API keys are stored in the same credential store as VM credentials. |
| **Android secret storage** | Android Keystore + EncryptedSharedPreferences | The paired API key and desktop public key are stored in the Keystore (hardware-backed when available). Never in plaintext SharedPreferences. |
| **Audit** | Existing audit_log (desktop) | Every API call is logged with timestamp, endpoint, VM name (if applicable), source IP (Tailscale IP), and success/failure. The Android app can view the audit log via the API. |
| **Rate limiting** | Simple token-bucket on the server | Prevent brute-force on `/api/v1/auth/pair` (rate limit by source IP). Other endpoints are rate-limited per API key. |

### 5.2 What the API Key Is Not

- It is NOT the VM password or SSH key — those stay in the desktop's credential store.
- It is NOT a Tailscale auth key — Tailscale handles its own node authentication.
- It is NOT stored on the desktop in plaintext — it's in the Fernet-encrypted credential store.

### 5.3 Android Keystore Usage

```kotlin
// Store the API key
val keyStore = KeyStore.getInstance("AndroidKeyStore")
keyStore.load(null)
val entry = KeyStore.SecretKeyEntry(generatedKey)
keyStore.setEntry("vmharness_api_key", entry, ProtectionParams.Builder()
    .setKeystoreEncryptionScope(KeystoreEncryptionScope.ICON_IN_MEMORY)
    .build())

// Or use EncryptedSharedPreferences (simpler, still Keystore-backed)
val masterKey = MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build()
val prefs = EncryptedSharedPreferences.create(
    context, "vmharness_paired_prefs", masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
)
prefs.edit().putString("api_key", secret).putString("host", host).apply()
```

The desktop public key (for pairing token verification) is stored as a raw asset in the Android app (`assets/desktop_public_key.pem`) — it's public, so no need to protect it. It's baked into the app at build time (or downloaded once and cached).

### 5.4 Pairing Token Verification on Android

```kotlin
// Pseudocode
fun verifyPairingToken(token: String, publicKey: PublicKey): PairingPayload? {
    val parts = token.split(".")
    if (parts.size != 2) return null
    val signatureBytes = Base64.decode(parts[0], Base64.URL_SAFE)
    val payloadBytes = Base64.decode(parts[1], Base64.URL_SAFE)
    
    // Verify signature
    val verifier = Signature.getInstance("SHA256withECDSA")
    verifier.initVerify(publicKey)
    verifier.update(payloadBytes)
    if (!verifier.verify(signatureBytes)) return null
    
    // Parse and validate payload
    val json = String(payloadBytes, Charsets.UTF_8)
    val payload = jsonToPayload(json)
    if (payload.kid != "v1") return null
    if (payload.purpose != "mobile-pairing") return null
    if (!payload.host.endsWith(".ts.net")) return null  // MagicDNS check
    if (!payload.ip.startsWith("100.")) return null       // Tailscale range check
    if (payload.expires != null && payload.expires < System.currentTimeMillis() / 1000) return null
    
    return payload  // contains secret, host, ip, etc.
}
```

### 5.5 Revocation & Key Rotation

- **Desktop revokes a device:** removes the API key from the credential store. The Android app gets 401 on next call and prompts re-pairing.
- **Desktop rotates its signing key:** generates a new ECDSA key pair, stores the new private key in the credential store, and distributes the new public key to all paired Android devices (via a `GET /api/v1/auth/public-key` endpoint that the Android app can call to refresh). Existing pairings remain valid until revoked.
- **Android loses the key:** re-pair via QR or manual entry.

### 5.6 Audit Trail

Every API call is logged by the desktop's `AuditLogger`:

```
timestamp | endpoint | method | source_ip (Tailscale) | api_key_id | vm_name | status | error
```

The Android app can view the audit log via `GET /api/v1/security/audit` — this gives the mobile user the same visibility as the desktop GUI's Security panel.

---

## 6. Android Tech Stack (Detailed)

### 6.1 Language & Runtime

- **Kotlin 1.9+** (coroutines, flows, sealed classes for UI state)
- **Minimum SDK:** 26 (Android 8.0 — covers 95%+ of active devices; Tailscale Android requires API 21+, so 26 is safe)
- **Target SDK:** 34 (Android 14) or latest
- **Compile SDK:** 34+

### 6.2 UI Framework

- **Jetpack Compose** (declarative, modern, lively explicitly)
- **Compose Material 3** (Material Design 3 components, theming)
- **Compose Navigation** (`androidx.navigation:navigation-compose`) for screen navigation
- **State management:** ViewModel + StateFlow / MutableState for UI state; sealed classes for screen states (`Loading`, `Success(data)`, `Error(message)`, `Unpaired`)

### 6.3 Networking

- **OkHttp** (`com.squareup.okhttp3:okhttp`) — HTTP client with interceptors for API key injection, logging, retry.
- **Retrofit** (`com.squareup.retrofit2:retrofit`) — type-safe REST API interfaces, generated implementations.
- **OkHttp WebSocket** (`okhttp3.WebSocket`) — for terminal, QMP console, metrics stream, log stream.
- **Kotlinx Serialization** (`org.jetbrains.kotlinx:kotlinx-serialization-json`) — JSON serialization for requests/responses (or Moshi — pick one; kotlinx-serialization is more modern and Kotlin-native).
- **Coil** (`io.coil-kt:coil-compose`) — image loading (for VM icons, avatars, etc., if needed).

### 6.4 Dependency Injection

- **Hilt** (`com.google.dagger:hilt-android`, `com.google.dagger:hilt-compiler`) — standard Android DI, integrates with ViewModel, OkHttp, Retrofit.
- Or **Koin** (`io.insert-koin:koin-android`, `io.insert-koin:koin-androidx-compose`) — lighter, more Kotlin-idiomatic, no annotation processing. Either is fine; Hilt is more "standard", Koin is more lightweight. Recommend Hilt for a production app with many dependencies, Koin for simplicity.

### 6.5 Data Storage

- **EncryptedSharedPreferences** (via AndroidX Security `androidx.security:security-crypto`) — for the paired API key, host, tailnet, machine_id, desktop public key (cached). Keystore-backed, simple.
- **Room** (`androidx.room:room-runtime`, `androidx.room:room-ktx`, `androidx.room:room-compiler`) — optional, for caching VM status, telemetry history, audit log entries, chat history locally. Not strictly required if everything is live from the API, but useful for offline reads and chart data retention.
- **DataStore** (`androidx.datastore:datastore-preferences`) — modern replacement for SharedPreferences for non-sensitive app preferences (theme, refresh interval, default VM, etc.).

### 6.6 QR Code Scanning

- **ML Kit Barcode Scanning** (`com.google.mlkit:barcode-scanning`) — Google's on-device barcode scanning, supports QR codes, fast, no server dependency. Integrates with Compose via a preview View (AndroidView) or a dedicated Compose camera library.
- **CameraX** (`androidx.camera:camera-camera2`, `camera-lifecycle`, `camera-view`) — camera preview for the QR scanner. ML Kit reads barcodes from the CameraX preview frames.
- Alternative: **Google Play Services ML Kit** via the Firebase ML Kit barcode library (same underlying tech, different artifact).

### 6.7 Charts & Visualization

- **Vico** (`com.patrykandpatrick.vico:compose`, `:core`, `:charmander`) — modern Compose-native charting library, clean API, good for CPU/RAM/disk/network time-series.
- Alternative: **MPAndroidChart** (matured, but Views-based, needs `AndroidView` wrapper in Compose — less ideal).
- Alternative: **Compose Charts** (Jetpack Compose charting, emerging — check latest stability).

### 6.8 Terminal / SSH UI

The guest terminal needs a terminal emulator UI in Compose. Options:

- **Almquist / TermiUX** — terminal emulators in pure Kotlin, but may not be Compose-native.
- **A custom Compose `TextField` + `Text` approach** for simple command output (less ideal — no ANSI color support, no cursor handling).
- **A WebView-based terminal** (embed a JS terminal emulator like xterm.js in a WebView) — works, but heavy.
- **A Compose Canvas-based terminal** — custom, but most control.
- **Recommendation:** Use a Compose `LazyColumn` + `TextField` for simple command input/output (REST SSH commands), and for the full interactive terminal, use a WebView hosting xterm.js (loaded from assets) with a JavaScript bridge that feeds stdin/stdout from the WebSocket. This gives full ANSI color, cursor, and resize support with minimal custom code.

### 6.9 Tailscale Detection (Android)

```kotlin
// Check if Tailscale is installed
val packageManager = context.packageManager
val tailscaleInstalled = packageManager.getPackageInfo("co.tailscale.tailscale", 0) != null
    || packageManager.getPackageInfo("com.tailscale.tailscale", 0) != null  // F-Droid variant

// Check if Tailscale VPN is active
val connectivityManager = context.getSystemService(ConnectivityManager::class.java)
val activeNetworks = connectivityManager.activeNetwork
val capabilities = connectivityManager.getNetworkCapabilities(activeNetworks)
val tailscaleActive = capabilities?.hasTransport(ConnectivityManager.TRANSPORT_VPN) == true
    || // more precise: check the VPN network's UID or package
```

A more reliable check: query `ConnectivityManager` for the active VPN network and check its underlying interface or the package that owns it. Or simply: try to resolve the desktop's MagicDNS hostname — if it resolves, Tailscale is working.

### 6.10 Build System

- **Gradle Kotlin DSL** (`build.gradle.kts`)
- **Android Gradle Plugin** 8.x
- **Jetpack Compose BOM** for version alignment
- **Custom Gradle plugin** or **build config** for the desktop public key asset (baked in at build time via a `res/raw` or `assets` file generated from the desktop's public key — in practice, the public key is distributed with the app, not generated per-build).

### 6.11 CI/CD for Android

- **GitHub Actions** — Android build + test + lint on push/PR.
- **F-Droid publishing** — if the app is FOSS (it should be, to match the desktop app's distribution model), F-Droid requires the app to build from source using their `fdroidserver` tool. Use standard Apache 2.0 / GPLv3 + QEMU exception licensing (same as desktop).
- **Google Play** — optional, if the user wants mainstream distribution. Requires a developer account, signing key, etc.

### 6.12 Signing & Security

- **Android app signing:** standard `keytool` generated keystore, stored securely (not in the repo). Use `androidx.biometric` optionally for app-open biometric lock (fingerprint/face) — a nice touch for a security-sensitive app.
- **API key in the app:** the desktop's ECDSA public key is baked into the app (public, no secrecy needed). The paired API key (secret) is stored at runtime in the Keystore.

---

## 7. Feature Parity Mapping

The desktop app has these GUI panels. Here's how each maps to the Android app:

| Desktop Panel | Android Screen | Parity Notes |
|---|---|---|
| **Dashboard** | Dashboard screen | VM list with status, host metrics, quick actions. Mobile layout: card grid or list. |
| **VM Control** | VM Control screen | Full VM detail, start/stop/reset/powerdown/pause/resume, config view. |
| **Guest Terminal** | Guest Terminal screen | WebSocket SSH terminal (xterm.js in WebView for full terminal, or REST commands + Compose UI for simple use). |
| **Telemetry** | Telemetry screen | CPU/RAM/disk/network charts (Vico), alerts list, history. |
| **Settings** | Settings screen | App settings, pairing management, desktop connection info, API key display (masked), logout/revoke. |
| **Security** | Security screen | Credential store view (list + detail — decrypted values require explicit consent on mobile), audit log viewer. |
| **Logs** | Logs screen | App log viewer, live tail via WebSocket. |
| **Multi-VM Switcher** | Multi-VM switcher | Active VM selector, mode toggle, quick actions on all VMs. |
| **Chat / Agent** | Chat screen | Chat interface, streaming agent responses (SSE or WebSocket). Mirrors desktop chat engine. |
| **ISO Manager** | ISO Manager screen (secondary) | ISO library list, add/remove, attach to VM. |
| **USB Passthrough** | USB config screen (secondary) | USB device list, attach/detach to VM. |
| **QMP Console** | QMP Console screen (secondary) | WebSocket QMP command/response. |
| **Snapshots** | Snapshots screen (secondary) | List/create/restore/delete snapshots, schedules. |
| **VM Cloner** | Clone screen (inline in VM Control) | Clone VM with name + config overrides. |
| **Network** | Network screen (secondary) | Network config view/edit, topology. |
| **Storage** | Storage screen (secondary) | Disk usage, VM disk sizes. |
| **AI Providers** | Providers screen (secondary) | Provider list, usage, config. |
| **System Info** | System Info screen (secondary) | Host CPU, RAM, OS, QEMU version, etc. |
| **Monitoring** | Monitoring screen (secondary) | Alerts, metrics, events dashboard. |
| **Troubleshoot** | Troubleshoot screen (secondary) | Connection diagnostics, status checks. |
| **Automation** | Automation screen (secondary) | Automation rules (if desktop has them). |
| **Guest Agent** | Guest Agent screen (secondary) | Guest agent status/controls. |
| **CPU Control** | CPU Control screen (secondary) | CPU pinning, topology. |
| **Display** | Display screen (secondary) | Display config. |

**Primary screens** (Dashboard, VM Control, Guest Terminal, Telemetry, Settings, Security, Logs) are the core — they get full UI and are front-and-center in the navigation. **Secondary screens** are accessible via the main navigation drawer or Settings, with simplified mobile UX (list + detail, fewer inline controls).

### 7.1 Mobile UX Adaptations

- **Bottom navigation** for primary screens (Dashboard, VMs, Terminal, Telemetry, Settings) — standard mobile pattern.
- **Navigation drawer** for secondary screens (Security, Logs, ISO, USB, Snapshots, Providers, etc.) — accessible from the top app bar or the drawer.
- **Detail screens** for VM config, credential details, snapshot details — push navigation from list items.
- **Floating action buttons (FAB)** for primary actions (start VM, send command, new snapshot) on relevant screens.
- **Pull-to-refresh** on list screens (VM list, credentials, logs) — refreshes from the API.
- **Swipe actions** on list items (e.g., swipe to stop VM, swipe to delete credential) — optional, for power users.
- **Search** on credential list, log list, snapshot list — filterable.
- **Dark theme** (mandatory — matches the desktop's Fusion dark theme; light theme optional).

---

## 8. UI/UX Design Language

### 8.1 Visual Identity

The Android app should visually echo the desktop app's aesthetic (Fusion dark theme, VM-Harness branding) but be idiomatic Android:

- **Dark theme as default** — matches the desktop. Light theme optional (system follow or toggle in Settings).
- **Color palette:** derive from the desktop's dark theme colors. Primary accent color for buttons, FAB, active states. Muted backgrounds for cards. Error red for destructive actions.
- **Typography:** system default (Roboto) or a clean sans-serif. Title, body, caption scales match Material 3.
- **Icons:** Material Icons (filled/outlined) for standard actions (play, stop, restart, terminal, settings, security, logs). Custom icons for VM-Harness-specific actions (QMP console, VM clone, snapshot) — simple vector drawables.
- **Cards** for VM list items — show name, status badge (running/stopped/paused), quick action icons.
- **Status badges:** color-coded (green = running, gray = stopped, yellow = paused, red = error/crashed).

### 8.2 Pairing / Welcome Screen

The first screen the user sees when the app is not yet paired:

```
┌────────────────────────────────┐
│  VM-Harness                      │
│  ┌──────────────────────────┐  │
│  │      [QR Code]           │  │
│  │      (scan to pair)      │  │
│  └──────────────────────────┘  │
│                                │
│  Pair your desktop             │
│                                │
│  Desktop: Omnarchy Workstation │
│  Host: omnarchy-vm.tail123... │
│  Tailnet: tail123              │
│                                │
│  [Scan QR]  [Enter Key Manually]│
│                                │
│  ── or ──                      │
│                                │
│  Make sure Tailscale is        │
│  running on both devices.      │
│  [Check Tailscale Status]      │
│                                │
│  Not paired yet?               │
│  Open VM-Harness on your         │
│  desktop → Settings →          │
│  Pair Mobile Device.           │
└────────────────────────────────┘
```

The QR code is generated by the **desktop** and displayed there. The Android app's pairing screen is the **scanner/receiver** — it scans the QR shown on the desktop, or accepts manual entry.

Wait — re-reading the user's request: "The API pairing key system must use a randomly generated key as well as bake in the proper network data from Tailscale and the machine, etc."

This means the pairing key is generated on the **desktop** (it has the Tailscale data + machine data), and the Android app receives it (via QR or manual entry). The Android app does NOT generate the key — it consumes it. The desktop is the pairing authority.

So the flow is:
1. Desktop generates the signed pairing token (with Tailscale host, IP, machine_id, random secret).
2. Desktop shows QR code + raw key string (in its GUI or headless output).
3. Android app scans QR or accepts manual entry.
4. Android validates the token, stores the secret, connects.

The Android app's "Pair" screen is the entry point — it either scans a QR (camera) or accepts a pasted key. It does NOT generate a key itself.

### 8.3 Dashboard Screen

```
┌────────────────────────────────┐
│  ← Back    VM-Harness      [⋮]  │
├────────────────────────────────┤
│  Omnarchy Workstation         │
│  ● Online · 100.123.45.67     │
├────────────────────────────────┤
│  [VM List / Quick Actions]     │
│                                │
│  ┌──────────────────────────┐  │
│  │ Ubuntu 24.04 VM          │  │
│  │ ▶ Running · 2h 14m       │  │
│  │ 2 vCPU · 4 GB RAM        │  │
│  │ [Stop] [Terminal] [⋮]   │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ Windows 11 VM            │  │
│  │ ■ Stopped                │  │
│  │ 4 vCPU · 8 GB RAM        │  │
│  │ [Start] [⋮]             │  │
│  └──────────────────────────┘  │
│                                │
│  [+ Add VM]  (if multi-VM)    │
├────────────────────────────────┤
│  Host Metrics                  │
│  CPU: 42%  RAM: 8.2/16 GB    │
│  Disk: 120/500 GB            │
└────────────────────────────────┘
```

### 8.4 VM Control Screen

```
┌────────────────────────────────┐
│  ← Back    Ubuntu 24.04 VM    │
├────────────────────────────────┤
│  ▶ Running                     │
│  Uptime: 2h 14m               │
│  vCPU: 2  RAM: 4 GB          │
│  Disk: 25 GB                  │
├────────────────────────────────┤
│  [Start] [Stop] [Reset]       │
│  [Pause] [Resume] [Powerdown] │
│  [Eject CDROM]                │
├────────────────────────────────┤
│  Network                      │
│  eth0: 192.168.122.100/24    │
│  SSH: omnarchy-vm:2222        │
├────────────────────────────────┤
│  QMP URI: localhost:4444     │
│  [Open QMP Console]           │
│  [Clone VM]                   │
│  [Snapshots]                  │
│  [USB Devices]                │
└────────────────────────────────┘
```

### 8.5 Guest Terminal Screen

```
┌────────────────────────────────┐
│  ← Back    Ubuntu 24.04 VM    │
│  Guest Terminal               │
├────────────────────────────────┤
│  ┌──────────────────────────┐  │
│  │  user@ubuntu:~$          │  │
│  │  ls -la                  │  │
│  │  total 42               │  │
│  │  drwxr-xr-x  ...         │  │
│  │  user@ubuntu:~$          │  │
│  │                          │  │
│  │  (xterm.js in WebView)   │  │
│  └──────────────────────────┘  │
│                                │
│  [Send Command] (REST fallback)│
└────────────────────────────────┘
```

For the REST command fallback (no WebSocket terminal), the screen is simpler:

```
┌────────────────────────────────┐
│  ← Back    Ubuntu 24.04 VM    │
│  Run Command                   │
├────────────────────────────────┤
│  [Command input field]         │
│  [Run]                         │
│                                │
│  Output:                       │
│  total 42                      │
│  drwxr-xr-x  ...              │
│  (exit code: 0)               │
│                                │
│  [History]  (previous commands)│
└────────────────────────────────┘
```

### 8.6 Telemetry Screen

```
┌────────────────────────────────┐
│  ← Back    Telemetry          │
├────────────────────────────────┤
│  ┌──────────────────────────┐  │
│  │  [CPU Chart]            │  │
│  │  0─60% over 1h          │  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │  [RAM Chart]            │  │
│  │  8.2 / 16 GB           │  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │  [Network I/O Chart]    │  │
│  └──────────────────────────┘  │
│                                │
│  [Alerts]  (tab)              │
│  [History] (tab)             │
└────────────────────────────────┘
```

### 8.7 Security Screen

```
┌────────────────────────────────┐
│  ← Back    Security           │
├────────────────────────────────┤
│  [Credentials]  [Audit Log]   │
│                                │
│  Credentials:                 │
│  ┌──────────────────────────┐  │
│  │ ✓ ssh_key_main           │  │
│  │ ✓ vm_password_ubuntu     │  │
│  │ ✓ qmp_token              │  │
│  └──────────────────────────┘  │
│                                │
│  [Add] [Search]               │
│                                │
│  Audit Log (last 50 entries): │
│  ┌──────────────────────────┐  │
│  │ 10:23:45 VM started     │  │
│  │ 10:22:10 SSH cmd run    │  │
│  │ ...                     │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

Decrypted credential values are shown only after an explicit "Show" tap, with a biometric prompt optionally (if the app has biometric lock enabled).

### 8.8 Settings Screen

```
┌────────────────────────────────┐
│  ← Back    Settings           │
├────────────────────────────────┤
│  Connected to:                │
│  Omnarchy Workstation         │
│  omnarchy-vm.tail123.ts.net   │
│  100.123.45.67               │
│  [Change] (re-pair)          │
│                                │
│  API Key:                     │
│  ●●●●●●●●●● (masked)        │
│  [Show] [Copy]               │
│                                │
│  Desktop App Version:         │
│  0.1.0                        │
│                                │
│  ── App Settings ──           │
│  Theme: 🌙 Dark               │
│  Refresh interval: 5s        │
│  Default VM: Ubuntu 24.04    │
│  Biometric lock: ✓ On        │
│                                │
│  ── About ──                  │
│  VM-Harness Android Companion   │
│  Version 1.0.0                │
│  [Check for updates]          │
│                                │
│  ── Danger Zone ──            │
│  [Revoke this device]         │
│  [Podcast desktop pairing]    │
└────────────────────────────────┘
```

---

## 9. Implementation Phases

### Phase 1: Foundation
- [ ] Project setup: Android Studio/IntelliJ project, Gradle Kotlin DSL, Compose BOM, Hilt/Koin, OkHttp/Retrofit, networking foundation.
- [ ] Desktop API server skeleton in the desktop app: `aiohttp`/`starlette` server, binding to Tailscale IP, basic auth middleware (API key check).
- [ ] Pairing token generation on desktop: ECDSA key pair in credential store, token sign/verify functions, QR code generation, Settings UI for "Pair Mobile Device".
- [ ] Android: Tailscale detection, pairing screen (QR scanner via ML Kit + CameraX, manual entry field), pairing token verification, PairingStore (EncryptedSharedPreferences/Keystore).
- [ ] Android: connection test — resolve MagicDNS, hit `GET /api/v1/auth/verify`, confirm the desktop is reachable and the key works.

**End of Phase 1:** The Android app can pair with the desktop via QR or manual entry, store the API key securely, and verify connectivity. The desktop API server is up, authenticated, and accepts the pairing.

### Phase 2: Core Parity
- [ ] Desktop API server: dashboard, VM list, VM lifecycle endpoints (start/stop/reset/powerdown/pause/resume/eject), VM detail endpoint.
- [ ] Android: Dashboard screen (VM list, status, quick actions, host metrics).
- [ ] Android: VM Control screen (detail, start/stop/reset/powerdown/pause/resume, network info, QMP URI, clone/snapshot/USB shortcuts).
- [ ] Desktop API server: SSH command endpoint, file operations (list/read/write/remove), terminal WebSocket.
- [ ] Android: Guest Terminal screen (REST command runner + WebSocket terminal via xterm.js WebView).

**End of Phase 2:** The Android app can view VMs, control their lifecycle, run SSH commands, and access the guest terminal — the core VM management parity.

### Phase 3: Observability
- [ ] Desktop API server: metrics endpoints (host + VM), metrics WebSocket stream, alerts, history, sysinfo.
- [ ] Android: Telemetry screen (Vico charts for CPU/RAM/disk/network, alerts list, history with time-range filter).
- [ ] Android: System Info screen (host CPU/RAM/OS/QEMU version).

**End of Phase 3:** The Android app has full visibility into host and VM telemetry, matching the desktop Telemetry panel.

### Phase 4: Security & Admin
- [ ] Desktop API server: credential store endpoints (list/detail/add/update/delete), audit log endpoint, settings endpoints (get/put), providers endpoints.
- [ ] Android: Security screen (credential list + detail with explicit "Show" + biometric, audit log viewer).
- [ ] Android: Settings screen (connection info, API key management, app preferences, biometric lock, revoke/repair).

**End of Phase 4:** The Android app has full security and admin parity — credentials, audit log, settings, providers.

### Phase 5: Secondary Features
- [ ] Desktop API server: logs endpoint + WebSocket, multi-VM endpoints, snapshot endpoints + schedules, ISO endpoints, USB endpoints, QMP console WebSocket, network/storage endpoints, chat endpoints (if applicable).
- [ ] Android: Logs screen (log list + live tail).
- [ ] Android: Multi-VM switcher (active VM selector, mode toggle, all-VM actions).
- [ ] Android: Snapshots screen (list/create/restore/delete, schedules).
- [ ] Android: ISO Manager screen.
- [ ] Android: USB config screen.
- [ ] Android: QMP Console screen (WebSocket).
- [ ] Android: Network screen, Storage screen, Providers screen, System Info screen, Monitoring screen, Troubleshoot screen.
- [ ] Android: Chat/Agent screen (if desktop has chat engine parity).

**End of Phase 5:** Full feature parity with the desktop GUI, mobile-adapted.

### Phase 6: Hardening & Polish
- [ ] Error handling: clear error states for all screens (connection lost, API key expired, desktop unreachable, Tailscale down, permission denied).
- [ ] Offline handling: if the desktop is unreachable, show a clear "Not connected" state with troubleshooting steps (check Tailscale, re-pair, restart desktop app).
- [ ] Biometric lock for app open (optional, `androidx.biometric`).
- [ ] Dark/light theme toggle (system follow or manual).
- [ ] Pull-to-refresh, swipe actions, search on list screens.
- [ ] App signing, build variants (debug/release), ProGuard/R8 rules.
- [ ] CI/CD: GitHub Actions Android build + test + lint, F-Droid build verification.
- [ ] Documentation: Android app README, pairing guide, troubleshooting.

---

## 10. Desktop API Server — Implementation Notes

### 10.1 Where It Lives

The API server is a new module in the desktop app, e.g., `gui/api_server.py` or `src/vm_mcp/api_server.py`. It's started from `main_window.py` (GUI mode) or `gui/__main__.py` (headless mode) after the bridges are initialized, sharing the same `QMPBridge`, `SSHBridge`, `CredentialStore`, `AuditLogger`, `Settings`, `Providers`, `ChatEngine`, etc.

### 10.2 Sharing State with the GUI

The API server does NOT duplicate any state. It holds references to the existing objects:

```python
class VM-HarnessApiServer:
    def __init__(self, settings, qmp_bridge, ssh_bridge, multi_vm_bridge,
                 credential_store, audit_logger, chat_engine, providers):
        self.settings = settings
        self.qmp_bridge = qmp_bridge
        self.ssh_bridge = ssh_bridge
        self.multi_vm_bridge = multi_vm_bridge
        self.credential_store = credential_store
        self.audit_logger = audit_logger
        self.chat_engine = chat_engine
        self.providers = providers
        # ... build aiohttp/starlette app with routes that call these ...
```

Each route handler calls the corresponding bridge method and returns the result as JSON. For async operations (QMP commands, SSH commands), the handlers are async and `await` the bridge's async methods.

### 10.3 Tailscale Detection

```python
import subprocess, json, socket

def get_tailscale_info() -> dict | None:
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        # Extract: TailscaleIP, MagicDNSSuffix, Tailnet, etc.
        return {
            "ip": data.get("TailscaleIPs", [None])[0],
            "magic_dns": data.get("MagicDNSSuffix"),
            "tailnet": data.get("Tailnet"),
            "running": True,
        }
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None
```

If `tailscale` CLI is not available, fall back to the Tailscale localhost API (port 9000) or simply check for a `100.x.y.z` interface via `socket` / `psutil`.

### 10.4 API Key Storage (Desktop)

The ECDSA signing key pair and the paired API keys are stored in the existing `CredentialStore`:

- **Signing key pair:** stored as a credential entry (e.g., `vmharness_signing_key`) — the private key is Fernet-encrypted, the public key is derivable.
- **Paired API keys:** each paired device gets a credential entry (e.g., `api_key_<machine_id_or_uuid>`) — the secret is Fernet-encrypted. The `machine_id` from the pairing token is the identifier.

### 10.5 Audit Logging for API Calls

Every API call is logged via the existing `AuditLogger`:

```python
async def log_api_call(endpoint, method, source_ip, api_key_id, vm_name, status, error=None):
    await audit_logger.log(
        event="api_call",
        details={
            "endpoint": endpoint,
            "method": method,
            "source_ip": source_ip,
            "api_key_id": api_key_id,
            "vm_name": vm_name,
            "status": status,
            "error": error,
        }
    )
```

### 10.6 Rate Limiting

Simple in-memory rate limiter per source IP and per API key:

```python
from collections import defaultdict
import time

class SimpleRateLimiter:
    def __init__(self, max_requests=60, window=60):
        self.max = max_requests
        self.window = window
        self.buckets = defaultdict(list)
    
    def allow(self, key: str) -> bool:
        now = time.time()
        bucket = self.buckets[key]
        bucket = [t for t in bucket if now - t < self.window]
        self.buckets[key] = bucket
        if len(bucket) >= self.max:
            return False
        bucket.append(now)
        return True
```

Apply to `/api/v1/auth/pair` (stricter, e.g., 5 per minute per IP) and other endpoints (e.g., 60 per minute per API key).

### 10.7 HTTPS vs HTTP

The API server runs **over HTTP** (not HTTPS) because Tailscale's WireGuard tunnels already encrypt all traffic. Adding TLS on top would require a certificate (self-signed, or Let's Encrypt for the MagicDNS name) and client cert verification — over-engineering for a trusted mesh network. The Tailscale encryption + API key is sufficient.

If the user wants HTTPS (e.g., for defense-in-depth or if the Tailscale tunnel is ever bypassed), the server can be configured to use a self-signed cert (generated on first run, stored in credential store) with `SSLContext` in `aiohttp`/`uvicorn`. But this is optional.

---

## 11. Desktop Side: Pairing UI

### 11.1 GUI Mode (Settings Panel)

Add a "Pair Mobile Device" section to the Settings panel (or a new Security sub-panel):

- Button "Generate Pairing Key" — generates a new signed token, displays QR code + raw key string.
- QR code widget (e.g., a `QGraphicsView` rendering a QR code from the `qrcode` Python library, or a bitmap from `qrcode.make()`).
- Raw key string (read-only text field, copyable).
- List of paired devices (machine_id, hostname, paired time) with "Revoke" button.
- "Pairing mode" toggle — when on, the API server accepts new pairings (otherwise, only existing keys work).

### 11.2 Headless Mode

When running headless (`--headless`), the pairing key is printed to stdout and/or saved to a file:

```
=== Mobile Pairing ===
Desktop: Omnarchy Workstation
Host: omnarchy-vm.tail123.ts.net
Tailscale IP: 100.123.45.67
Tailnet: tail123
Machine ID: sha256:a1b2c3d4...

Pairing QR (scan with VM-Harness Android app):
[QR code as ASCII or saved to pairing_qr.png]

Pairing Key (manual entry):
vmharness://pair?key=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...

Pairing mode: ON
Press Ctrl+C to stop.
```

### 11.3 QR Code Generation (Python)

```python
import qrcode

def generate_qr_code(token_uri: str) -> bytes:
    # token_uri = "vmharness://pair?key=..."
    qr = qrcode.make(token_uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    return buffer.getvalue()
```

The PNG bytes can be displayed in the GUI (as a `QPixmap`) or saved to a file in headless mode. The `qrcode` library is a lightweight dependency — add it to `pyproject.toml` if not already present.

---

## 12. Android Side: Pairing Implementation

### 12.1 QR Scanner (ML Kit + CameraX)

```kotlin
// CameraX preview in Compose via AndroidView
@Composable
fun CameraPreview(
    analyzer: ImageAnalysis.Analyzer,
    modifier: Modifier = Modifier
) {
    AndroidView(
        factory = { ctx ->
            val preview = Preview.Builder().build()
            val analyzer = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
            analyzer.setAnalyzer(ExecutorCompat(Executors.newSingleThreadExecutor())) { image ->
                analyzer.analyze(image)
            }
            preview.setSurfaceProvider(...)
            // bind to lifecycle
            preview
        }
    )
}

// ML Kit barcode scanning
val scanner = BarcodeScanning.getClient()
scanner.process(holder.getImage())
    .addOnSuccessListener { barcodes ->
        for (barcode in barcodes) {
            if (barcode.valueType == Barcode.TYPE_URL) {
                val uri = barcode.displayValue
                if (uri.startsWith("vmharness://pair?")) {
                    // Extract key parameter
                    val key = Uri.parse(uri).getQueryParameter("key")
                    handlePairingKey(key)
                }
            }
        }
    }
```

### 12.2 Pairing Key Verification

```kotlin
data class PairingPayload(
    val kid: String,
    val purpose: String,
    val host: String,
    val ip: String,
    val tailnet: String,
    val machineId: String,
    val created: Long,
    val expires: Long?,
    val secret: String
)

fun verifyAndParseToken(
    token: String,
    publicKey: PublicKey
): Result<PairingPayload> {
    val parts = token.split(".")
    if (parts.size != 2) return Result.failure(IllegalArgumentException("Invalid token format"))
    
    val sigBytes = Base64.decode(parts[0], Base64.URL_SAFE)
    val payloadBytes = Base64.decode(parts[1], Base64.URL_SAFE)
    
    val verifier = Signature.getInstance("SHA256withECDSA")
    verifier.initVerify(publicKey)
    verifier.update(payloadBytes)
    if (!verifier.verify(sigBytes)) return Result.failure(IllegalArgumentException("Signature invalid"))
    
    val json = String(payloadBytes, Charsets.UTF_8)
    val payload = jsonToPayload(json)  // kotlinx-serialization reflection
    
    // Validate fields
    require(payload.kid == "v1") { "Unsupported kid: ${payload.kid}" }
    require(payload.purpose == "mobile-pairing") { "Wrong purpose" }
    require(payload.host.endsWith(".ts.net")) { "Not a MagicDNS name: ${payload.host}" }
    require(payload.ip.startsWith("100.")) { "Not a Tailscale IP: ${payload.ip}" }
    require(payload.expires == null || payload.expires > System.currentTimeMillis() / 1000) { "Token expired" }
    
    return Result.success(payload)
}
```

### 12.3 PairingStore

```kotlin
class PairingStore(context: Context) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    private val prefs = EncryptedSharedPreferences.create(
        context, "vmharness_paired",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    
    var apiKey: String?
        get() = prefs.getString("api_key", null)
        set(value) = prefs.edit().putString("api_key", value).apply()
    
    var host: String?
        get() = prefs.getString("host", null)
        set(value) = prefs.edit().putString("host", value).apply()
    
    var ip: String?
        get() = prefs.getString("ip", null)
        set(value) = prefs.edit().putString("ip", value).apply()
    
    var tailnet: String?
        get() = prefs.getString("tailnet", null)
        set(value) = prefs.edit().putString("tailnet", value).apply()
    
    var machineId: String?
        get() = prefs.getString("machine_id", null)
        set(value) = prefs.edit().putString("machine_id", value).apply()
    
    var desktopPublicKey: String?
        get() = prefs.getString("desktop_public_key", null)
        set(value) = prefs.edit().putString("desktop_public_key", value).apply()
    
    fun clear() {
        prefs.edit().clear().apply()
    }
    
    val isPaired: Boolean get() = apiKey != null && host != null
}
```

### 12.4 API Client (OkHttp + Retrofit)

```kotlin
interface VM-HarnessApi {
    // Auth
    @POST("api/v1/auth/pair")
    suspend fun pair(@Body pairRequest: PairRequest): PairResponse
    
    @GET("api/v1/auth/verify")
    suspend fun verify(): VerifyResponse
    
    // Dashboard + VMs
    @GET("api/v1/")
    suspend fun dashboard(): DashboardResponse
    
    @GET("api/v1/vms")
    suspend fun listVms(): List<VmSummary>
    
    @GET("api/v1/vms/{name}")
    suspend fun getVm(@Path("name") name: String): VmDetail
    
    @POST("api/v1/vms/{name}/start")
    suspend fun startVm(@Path("name") name: String)
    
    @POST("api/v1/vms/{name}/stop")
    suspend fun stopVm(@Path("name") name: String, @Query("graceful") graceful: Boolean = true)
    
    @POST("api/v1/vms/{name}/reset")
    suspend fun resetVm(@Path("name") name: String)
    
    // ... etc for all endpoints ...
}

// Auth interceptor
class ApiKeyInterceptor(private val apiKey: String) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request().newBuilder()
            .addHeader("X-API-Key", apiKey)
            .build()
        return chain.proceed(request)
    }
}

// OkHttp setup
val client = OkHttpClient.Builder()
    .addInterceptor(ApiKeyInterceptor(pairingStore.apiKey!!))
    .addInterceptor(HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC })
    .build()

val api = Retrofit.Builder()
    .baseUrl("http://${pairingStore.host}:8443/")  // or the IP directly
    .client(client)
    .addConverterFactory(Json.asConverterFactory("application/json".toMediaType()))
    .build()
    .create(VM-HarnessApi::class.java)
```

Note: the base URL uses the MagicDNS host — OkHttp will resolve it via DNS (which, when Tailscale is active, resolves to the Tailscale IP). Alternatively, use the IP directly (`http://100.123.45.67:8443/`) — the IP is baked into the pairing token.

### 12.5 WebSocket Terminal

```kotlin
// OkHttp WebSocket for SSH terminal
val webSocket = client.newWebSocket(
    Request.Builder()
        .url("http://${host}:8443/api/v1/vms/${vmName}/terminal")
        .build(),
    object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            // Send auth first
            webSocket.send("""{"type":"auth","key":"$apiKey"}""")
        }
        
        override fun onMessage(webSocket: WebSocket, text: String) {
            val msg = jsonToMessage(text)
            when (msg.type) {
                "stdout" -> terminalOutput += msg.data
                "stderr" -> terminalOutput += msg.data
                "resize" -> sendResize(msg.cols, msg.rows)
                // ...
            }
        }
        
        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            // Handle disconnect
        }
    }
)

// Send stdin
fun sendCommand(cmd: String) {
    webSocket.send("""{"type":"stdin","data":"$cmd"}""")
}
```

### 12.6 Metrics WebSocket (Live Charts)

```kotlin
// Metrics stream for Vico charts
val metricsWebSocket = client.newWebSocket(
    Request.Builder()
        .url("http://${host}:8443/api/v1/metrics/stream")
        .build(),
    object : WebSocketListener() {
        override fun onMessage(webSocket: WebSocket, text: String) {
            val msg = jsonToMessage(text)
            if (msg.type == "metric") {
                val data = msg.data as Map
                val cpu = data["cpu"] as Double
                val ram = data["ram"] as Double
                // Add to Vico chart data
                chartModel.addEntry(cpu, ram, System.currentTimeMillis())
            }
        }
    }
)
```

---

## 13. Dependency Summary

### Desktop (Python) — new dependencies

| Package | Purpose | Adding to pyproject.toml? |
|---|---|---|
| `aiohttp` (or `starlette` + `uvicorn`) | API server framework | Yes (if not already) |
| `qrcode` | QR code generation for pairing | Yes (lightweight) |
| `cryptography` (already present) | ECDSA key pair for signing tokens | Already a dependency (via credential_store's Fernet) |
| `pydantic` (already present) | Request/response validation models | Already a dependency |

The ECDSA signing key is generated with `cryptography.hazmat.primitives.asymmetric.ec`.

### Android (Kotlin) — dependencies (build.gradle.kts)

```kotlin
dependencies {
    // Compose BOM
    val composeBom = platform("androidx.compose:compose-bom:2024.02.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.navigation:navigation-compose:2.7.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    
    // Networking
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-kotlinx-serialization:2.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    
    // DI
    implementation("com.google.dagger:hilt-android:2.50")
    kapt("com.google.dagger:hilt-android-compiler:2.50")
    // or Koin:
    // implementation("io.insert-koin:koin-android:3.5.3")
    // implementation("io.insert-koin:koin-androidx-compose:3.5.3")
    
    // Storage
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    implementation("androidx.datastore:datastore-preferences:1.0.0")
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    kapt("androidx.room:room-compiler:2.6.1")
    
    // QR + Camera
    implementation("com.google.mlkit:barcode-scanning:17.2.0")
    implementation("androidx.camera:camera-camera2:1.3.1")
    implementation("androidx.camera:camera-lifecycle:1.3.1")
    implementation("androidx.camera:camera-view:1.3.1")
    
    // Charts
    implementation("com.patrykandpatrick.vico:compose:1.13.1")
    implementation("com.patrykandpatrick.vico:core:1.13.1")
    implementation("com.patrykandpatrick.vico:charmander:1.13.1")
    
    // Biometric (optional)
    implementation("androidx.biometric:biometric:1.1.0")
    
    // WebView for terminal (xterm.js)
    // (no extra dependency — Android has WebView built in)
    
    // Testing
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation(composeBom)
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
```

---

## 14. Security Checklist

- [ ] API server binds only to Tailscale IP (or 0.0.0.0 with `100.0.0.0/8` source filter) — no localhost-only, no LAN exposure.
- [ ] API key required on every endpoint (except `/auth/pair` and `/auth/verify` which have their own auth).
- [ ] Pairing tokens are ECDSA-signed by the desktop, verifiable by the Android app's baked-in public key.
- [ ] The API key secret is random 256-bit, not derivable from the metadata.
- [ ] Android API key stored in EncryptedSharedPreferences / Keystore, never in plaintext.
- [ ] Desktop signing key + paired API keys stored in Fernet-encrypted credential store.
- [ ] Audit log records every API call (endpoint, source IP, VM, status).
- [ ] Rate limiting on `/auth/pair` (prevent brute-force) and other endpoints.
- [ ] Credential decryption on Android requires explicit user consent (Show button, optional biometric).
- [ ] Pairing can be revoked from both desktop and Android.
- [ ] Tailscale detection on Android — app doesn't crash if Tailscale isn't running, shows clear error.
- [ ] No hardcoded IPs or secrets in the Android app (only the desktop public key, which is public).

---

## 15. Open Questions & Decisions

1. **HTTPS or HTTP on the API server?** Recommendation: HTTP over Tailscale (WireGuard encryption is sufficient). Add HTTPS as an optional config if the user wants defense-in-depth. No decision needed now — start with HTTP, add HTTPS later if requested.

2. **ECDSA curve for signing keys?** `secp256r1` (prime256v1) — widely supported, 128-bit security, small signatures. Good choice. Or `Ed25519` — smaller keys/signatures, modern, also widely supported in `cryptography`. Either works; Ed25519 is slightly cleaner. Recommendation: Ed25519.

3. **What port for the API server?** `8443` (conventional HTTPS alternate) or `8080` (conventional HTTP). Since we're using HTTP over Tailscale, `8080` is fine. Or a custom port like `50922` (arbitrary, unlikely to conflict). Recommendation: `8443` (signals "privileged API" even though it's HTTP) or `50922`. Pick one and document it.

4. **Does the Android app support multiple paired desktops?** The current design is one desktop per app install (simplest). Multi-device support (switch between desktops) is a Phase 6+ feature. For now, one pairing per app install.

5. **Does the Android app cache data locally (Room)?** For full parity, caching VM status, telemetry history, audit log entries, and chat history locally is useful (offline reads, chart data retention). Start without Room (live API only) and add Room in Phase 6 if needed.

6. **Terminal UI: xterm.js in WebView or pure Compose?** xterm.js in WebView gives full ANSI color/cursor/resize support with minimal custom code. Pure Compose terminal is more "native" but requires significant custom work for parity. Recommendation: xterm.js in WebView for the interactive terminal, REST command runner as a fallback/simpler option.

7. **F-Droid distribution?** The Android app should be FOSS (Apache 2.0 or GPLv3 + QEMU exception, matching the desktop). F-Droid requires building from source — ensure the build is reproducible (no proprietary deps, no Google Play Services required — ML Kit barcode scanning works without Play Services via the on-device model). If F-Droid is a goal, avoid Play Services dependencies that aren't on F-Droid. ML Kit barcode scanning is available as a standalone artifact that works without Play Services.

---

## 16. Deliverables Summary

### Desktop Changes (Python)
1. **`gui/api_server.py`** (or `src/vm_mcp/api_server.py`) — aiohttp/starlette server with all endpoints in §4.
2. **`gui/panels_settings.py`** (or new panel) — "Pair Mobile Device" UI: QR code display, raw key, paired device list, revoke.
3. **`gui/__main__.py`** — in headless mode, print pairing info to stdout.
4. **Tailscale detection** — `get_tailscale_info()` function, used by API server binding and pairing UI.
5. **ECDSA signing key** — generated once, stored in credential store, used to sign pairing tokens.
6. **Audit logging** — API calls logged via existing `AuditLogger`.
7. **`pyproject.toml`** — add `aiohttp` (or `starlette`+`uvicorn`) and `qrcode` as dependencies.
8. **Updated `SECURITY_AUDIT.md`** — document the API key pairing system, Tailscale binding, rate limiting, Android Keystore usage.

### Android Changes (Kotlin)
1. **Full Android project** — Gradle Kotlin DSL, Compose, Hilt/Koin, all dependencies.
2. **Pairing screen** — QR scanner (ML Kit + CameraX), manual entry, token verification, PairingStore.
3. **Dashboard screen** — VM list, status, quick actions, host metrics.
4. **VM Control screen** — detail, lifecycle actions, network/QMP info, clone/snapshot/USB shortcuts.
5. **Guest Terminal screen** — WebSocket terminal (xterm.js WebView) + REST command runner.
6. **Telemetry screen** — Vico charts, alerts, history.
7. **Security screen** — credentials (list + detail with consent), audit log.
8. **Settings screen** — connection info, API key management, app prefs, biometric lock, revoke.
9. **Logs screen** — log list + live tail.
10. **All secondary screens** — Multi-VM, Snapshots, ISO, USB, QMP Console, Network, Storage, Providers, System Info, Monitoring, Troubleshoot, Chat (as parity requires).
11. **API client** — Retrofit/OkHttp with API key interceptor, WebSocket clients for terminal/metrics/logs/QMP.
12. **CI/CD** — GitHub Actions Android build + test + lint, F-Droid verification.

---

*End of design document.*

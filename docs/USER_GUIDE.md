# VM-Harness User Guide

**Complete QEMU Virtual Machine Control Suite**

Control QEMU virtual machines through a PyQt5 desktop GUI, CLI, REST API, or MCP server. Also includes Docker container management, Kubernetes orchestration, VMware/VirtualBox management, live console streaming, and image pull monitoring.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
   - [First Launch](#first-launch)
2. [VM Management](#2-vm-management)
   - [Starting a VM](#starting-a-vm)
   - [Stopping a VM](#stopping-a-vm)
   - [Snapshots](#snapshots)
   - [Multi-VM Management](#multi-vm-management)
3. [Container Management](#3-container-management)
   - [Listing Containers](#listing-containers)
   - [Starting & Stopping Containers](#starting--stopping-containers)
   - [Container Terminal](#container-terminal)
   - [Container Stats](#container-stats)
   - [Container Logs](#container-logs)
4. [Kubernetes Management](#4-kubernetes-management)
   - [Pods, Deployments & Services](#pods-deployments--services)
   - [YAML Editor](#yaml-editor)
   - [Resource Tree View](#resource-tree-view)
5. [VMware & VirtualBox Management](#5-vmware--virtualbox-management)
6. [VM Console Streaming](#6-vm-console-streaming)
7. [Image Pull Progress](#7-image-pull-progress)
8. [Settings & Configuration](#8-settings--configuration)
9. [TLS/SSL Setup](#9-tlsssl-setup)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Getting Started

### Prerequisites

| Requirement | Minimum | Recommended | Notes |
|-------------|---------|-------------|-------|
| **Python** | 3.10 | 3.11 or 3.13 | 3.11+ for full async support |
| **QEMU** | 7.0 | 8.x+ | `qemu-system-x86_64.exe` on Windows |
| **Windows** | 10 | 11 | WHPX requires Windows 10 1903+ |
| **RAM** | 8 GB | 16 GB+ | 4 GB minimum for host + VM |
| **Disk Space** | 10 GB | 50 GB+ | For VM images and application |
| **Git** | 2.30+ | Latest | For cloning repository |

**Recommended Windows Features** (PowerShell as Administrator):

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName WindowsHypervisorPlatform
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
# Restart required
```

### Installation

#### From Source

```bash
git clone https://github.com/your-org/qemu-mcp.git
cd qemu-mcp
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/macOS
pip install -e ".[dev]"
```

This installs PyQt5, mcp[cli], pydantic, asyncssh, cryptography, matplotlib, psutil, aiohttp, loguru, and pytest.

#### Standalone Executable

A pre-built `dist/VM-Harness.exe` (PyInstaller) is available -- no Python installation required. Extract to any folder and run.

#### Configure QEMU Path

Create or edit `.env` in the project root:

```env
QEMU_BINARY="C:/Program Files/qemu/qemu-system-x86_64.exe"
QEMU_EXTRA_ARGS="-machine q35,kernel_platform="
VM_NAME="omarchy-vm"
VM_DISK="C:/Users/Server/Virtual Machines/omarchy-vm/disk.qcow2"
VM_ISO=""
VM_RAM_MB="16384"
VM_CPUS="8"
VM_HOSTNAME="omarchy-vm"
DISPLAY="SDL"
OPENGL="1"
AUTO_EJECT_ISO="1"
VM_ACCELERATION="whpx"
SSH_HOST="127.0.0.1"
SSH_PORT="2222"
SSH_USERNAME="omarchyvm"
LOG_LEVEL="INFO"
AUTH_METHOD="api_key"
```

### First Launch

```bash
# Launch the GUI
qemu-mcp gui

# Check system status via CLI
qemu-mcp status

# Verify QEMU installation
qemu-system-x86_64 --version
```

**Screenshot Description:** *The VM-Harness main window opens with a dark-themed UI. The left sidebar shows 24 icon+label navigation buttons. The main content area displays the Dashboard panel by default, showing VM status (state, PID, RAM, vCPUs, disk, uptime), quick action buttons (Start VM, Stop VM, Reset VM), and a recent activity log. The top shows a custom title bar with the app name "VM-Harness", a status indicator dot, and window controls.*

---

## 2. VM Management

### Starting a VM

**GUI Method:**

1. Launch the GUI -- the Dashboard panel opens by default
2. Verify settings in **Settings > QEMU** and **Settings > VM** tabs
3. Click **Start VM** on the Dashboard
4. The status indicator turns green; the QEMU process starts with QMP, SSH port forwarding, and configured display

**CLI Method:**

```bash
qemu-mcp vm start omarchy-vm
```

**Screenshot Description:** *The Dashboard panel shows a large status card. When stopped, the status reads "Stopped" with a gray dot. After clicking Start VM, the status changes to "Running" with a green dot, and fields populate: PID (e.g., 12345), RAM (16 GB), vCPUs (8), Disk usage, and Uptime counter.*

**What Happens Behind the Scenes:**

- QEMU is launched with: `-machine q35 -m <RAM> -smp <CPUs> -drive file=<disk>,format=qcow2 -qmp tcp:127.0.0.1:4444,server,nowait -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22`
- The QMP bridge connects to the QMP socket for lifecycle control
- The SSH bridge is ready to accept guest connections on port 2222
- The process guardian begins monitoring the QEMU process

### Stopping a VM

**GUI Method:** Click **Stop VM** on the Dashboard or VM Control panel. This sends a graceful ACPI powerdown via QMP `system_powerdown`.

**CLI Method:**

```bash
qemu-mcp vm stop omarchy-vm
```

**Other Lifecycle Operations:**

| Operation | QMP Command | Button Location |
|-----------|-------------|-----------------|
| **Start** | `cont` | Dashboard, VM Control |
| **Stop** | `system_powerdown` | Dashboard, VM Control |
| **Reset** | `system_reset` | Dashboard, VM Control |
| **Suspend** | `stop` | VM Control |
| **Resume** | `cont` | VM Control |
| **Eject ISO** | `eject` | VM Control |

### Snapshots

Snapshots capture the complete disk state at a point in time via `qemu-img`.

**Creating a Snapshot:**

1. Go to **Snapshots** panel
2. Click **Create**
3. Enter a snapshot name (e.g., `backup-2026-09-23`)
4. Click OK

**Screenshot Description:** *The Snapshots panel shows a table listing all snapshots with columns for Name, Size, Created date, and Actions. The Create button is in the toolbar. Below the table, Restore and Delete buttons operate on the selected snapshot.*

**Restoring a Snapshot:**

1. Select the snapshot in the list
2. Click **Restore**
3. Confirm -- *"Restoring discards all changes since the snapshot was created"*

**CLI Method:**

```bash
qemu-mcp snapshot create my-backup
qemu-mcp snapshot list
qemu-mcp snapshot restore my-backup
```

**Backend Commands:**

```bash
qemu-img snapshot -c <name> <disk-path>   # Create
qemu-img snapshot -a <name> <disk-path>   # Restore (apply)
qemu-img snapshot -d <name> <disk-path>   # Delete
qemu-img snapshot -l <disk-path>          # List
```

### Multi-VM Management

The **VM Switcher** panel manages multiple VMs from one interface.

**Screenshot Description:** *The VM Switcher panel shows a list of registered VMs with status indicators (green=running, gray=stopped, yellow=paused). Action buttons include Add VM, Switch To, Remove, Start, Stop, Clone, and Templates. Below the list, a details card shows the selected VM's name, QMP URI, SSH URI, RAM, and vCPUs. Resource limits (Max RAM, Max vCPUs, Priority) have spinboxes with an Apply Limits button.*

**Adding a VM:**

1. Click **Add VM**
2. Enter VM name and select a disk image (.qcow2, .img, .vmdk, .raw)
3. Configure RAM, CPUs, and display
4. Click OK

**Switching Between VMs:**

1. Select a VM in the list
2. Click **Switch To** (or double-click the entry)
3. All other panels now target the selected VM

**Resource Limits:**

| Limit | Range | Default | Description |
|-------|-------|---------|-------------|
| Max RAM | 512 MB - 131072 MB | 4096 MB | Maximum memory the VM can use |
| Max vCPUs | 1 - 128 | 2 | Maximum CPU cores |
| Priority | 1 (highest) - 10 (lowest) | 5 | Scheduling priority |

---

## 3. Container Management

VM-Harness includes a full Docker container management suite accessible via the **Container** panel.

**Screenshot Description:** *The Container panel shows a "Backend Status" card at top with three status indicators: Docker, Kubernetes, and Podman. Green means connected, red means unavailable. Below is a tabbed interface with four tabs: Containers, Images, Kubernetes, and Podman. The Containers tab shows a filter dropdown (All/Running/Stopped/Paused), action buttons (Start, Stop, Restart, Logs, Exec, Remove), and a table listing containers with Name, Image, Status, and Ports columns.*

### Listing Containers

1. Open the **Container** panel from the sidebar
2. The **Containers** tab is shown by default
3. Use the filter dropdown to show: All, Running, Stopped, or Paused containers
4. The table auto-refreshes every 10 seconds

**Container Table Columns:**

| Column | Description |
|--------|-------------|
| Name | Container name |
| Image | Source Docker image (e.g., `ubuntu:22.04`) |
| Status | Running, Exited, Paused, Restarting |
| Ports | Port mappings (e.g., `0.0.0.0:8080->80/tcp`) |

### Starting & Stopping Containers

1. Select a container in the table (click its row)
2. Click **Start** to start a stopped container
3. Click **Stop** to stop a running container (sends SIGTERM, then SIGKILL after timeout)
4. Click **Restart** to stop and immediately restart

**Removing a Container:**

1. Select the container
2. Click **Remove**
3. Confirm -- the container is permanently deleted

### Container Terminal

The **Container Terminal** panel provides an interactive shell inside any Docker container via WebSocket.

**Screenshot Description:** *The Container Terminal panel shows a connection status card with a "WebSocket" indicator, a container selector dropdown, and Connect/Disconnect/Clear buttons. Below is a monospace terminal output area (dark background #0d1117, light text #c9d1d9) and a command input row with a "$" prompt. At the bottom, a "Quick Commands" card has buttons for: ls, pwd, ps aux, df -h, free -m, uname -a, cat /etc/os-release.*

**Using the Terminal:**

1. Select a container from the dropdown (shows `name (status)`)
2. Click **Connect** -- establishes WebSocket connection to `ws://127.0.0.1:8445/terminal/<container>`
3. Type commands in the input field and press Enter (or click Send)
4. Output appears in the terminal area in real-time
5. Click **Disconnect** when finished

**Quick Commands:** Click any button in the Quick Commands card to instantly run common commands.

**Requirements:**
- The VM or Docker host must be running
- WebSocket bridge service must be active on port 8445
- The container must have a shell available

### Container Stats

The **Container Stats** panel shows real-time resource usage for all containers.

**Screenshot Description:** *The Container Stats panel has two header stat cards: "Total Containers" and "Running". Below is a vertical splitter with a container table (Container, Status) on top and a detail view on the bottom. The detail view shows two sparkline charts side-by-side: CPU History (blue, #60a5fa) and Memory History (purple, #a78bfa). Below the charts are large labels showing current CPU % and memory usage in MB. A detail info area shows container name, status, uptime, and image. At the bottom, a "Refresh Now" button, "Auto-refresh: ON (2s)" label, and Docker status indicator.*

**Metrics Displayed:**

| Metric | Description | Refresh |
|--------|-------------|---------|
| CPU % | Current CPU utilization | 2 seconds |
| Memory | Current memory usage in MB | 2 seconds |
| CPU History | Sparkline of last 60 data points | Continuous |
| Memory History | Sparkline of last 60 data points | Continuous |

### Container Logs

View container logs via the **Logs** button on the Containers tab, or directly in the **Container Logs** dialog.

**Screenshot Description:** *The Container Logs dialog shows a header with the container name and a status indicator. Below is a toolbar with Refresh button, a "Tail" dropdown (50/100/200 lines), and an "Auto-refresh: OFF/ON" toggle. The main area is a monospace QTextBrowser showing log output. A status bar at the bottom shows "Last updated: HH:MM:SS - tail=100".*

**Using Container Logs:**

1. On the Containers tab, select a container
2. Click **Logs**
3. The dialog opens and fetches logs from `GET /api/v1/containers/<name>/logs?tail=<N>`
4. Use the **Tail** dropdown to control how many lines to show (50, 100, or 200)
5. Toggle **Auto-refresh** to poll for new logs every 5 seconds
6. Click **Refresh** for a manual update

---

## 4. Kubernetes Management

VM-Harness provides Portainer-equivalent Kubernetes management through two dedicated panels.

### Pods, Deployments & Services

The **Kubernetes Editor** panel provides a split-view interface with a resource tree on the left and a YAML manifest editor on the right.

**Screenshot Description:** *The Kubernetes Editor panel shows a "Kubernetes Status" card at top with a cluster indicator dot, a namespace selector dropdown, and a Refresh button. Below is a horizontal splitter: the left side has a "Resources" tree widget with columns (Name, Type, Status) showing Kubernetes resources organized by namespace. The right side has a "YAML Manifest" editor (dark monospace editor with placeholder text "Select a resource to view its YAML, or write a new manifest here..."). Below the editor are four buttons: Apply (green), Delete (red), Validate, and New. Auto-refresh runs every 15 seconds.*

**Browsing Resources:**

1. Select a namespace from the dropdown (or "All Namespaces")
2. The resource tree populates with Deployments, Pods, Services, and other resources
3. Each item shows a colored status dot:
   - Green: Running, Active, Ready, Succeeded, Healthy
   - Yellow: Pending, ContainerCreating, Terminating, Initializing
   - Red: Error, Failed, CrashLoopBackOff, ImagePullBackOff, Evicted
   - Gray: Unknown

4. Double-click a resource to load its YAML manifest in the editor

### YAML Editor

**Editing and Applying Manifests:**

1. **View:** Double-click any resource in the tree to load its YAML
2. **Edit:** Modify the YAML in the editor (Consolas monospace font, dark background)
3. **Validate:** Click **Validate** to check the manifest for syntax errors before applying
4. **Apply:** Click **Apply** to create or update the resource in the cluster
5. **New:** Click **New** to clear the editor and write a manifest from scratch
6. **Delete:** Select a resource in the tree, then click **Delete** to remove it from the cluster

**Example Manifest:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
        ports:
        - containerPort: 80
```

### Resource Tree View

The **Kubernetes Tree** panel provides a hierarchical view of all Kubernetes resources.

**Screenshot Description:** *The Kubernetes Tree panel shows a "Kubernetes Cluster" status card with a cluster indicator, namespace dropdown, and Refresh button. Below is a horizontal splitter: the left side shows a "Resource Hierarchy" tree widget with columns (Status dot, Name, Type, Status). The tree is expandable -- namespaces at the top level, with child nodes for Deployments, Pods, Services, etc. The right side shows a YAML editor with a "YAML Manifest" header. A context menu on the tree items offers "Delete" and "Write YAML" actions. Auto-refresh polls every 10 seconds when the panel is visible, and stops when hidden.*

**Tree Hierarchy:**

```
default
  Deployment: nginx-deployment (3/3 ready) [green]
    Pod: nginx-deployment-abc12 (Running) [green]
    Pod: nginx-deployment-def34 (Running) [green]
    Pod: nginx-deployment-ghi56 (Running) [green]
  Service: nginx-service (ClusterIP) [green]
  ConfigMap: nginx-config [green]
kube-system
  Pod: coredns-abc12 (Running) [green]
  Service: kube-dns (ClusterIP) [green]
```

**Context Menu Actions:**

| Action | Description |
|--------|-------------|
| **Delete** | Delete the selected resource from the cluster |
| **Write YAML** | Export the resource's YAML to the editor pane |

---

## 5. VMware & VirtualBox Management

The **VMware/VirtualBox** panel provides unified management for non-QEMU hypervisors.

**Screenshot Description:** *The VMware/VBox panel shows a "Hypervisor Status" card at top with two status indicators: VMware (red/green dot) and VirtualBox (red/green dot), plus a Refresh button. Below is a tabbed interface with two tabs: "VMware" and "VirtualBox". The VMware tab has a filter dropdown (All/Powered On/Powered Off/Suspended), action buttons (Power On, Power Off, Suspend, Reset, Snapshot), and a VM table with columns (Name, Guest OS, State, IP Address). Below the table is a "VMware Snapshots" card with a text browser showing snapshot details. The VirtualBox tab has a filter dropdown (All/Running/Powered Off/Paused), action buttons (Start, Stop, Pause, Reset), and a table with columns (Name, OS Type, State, Memory).*

**VMware Operations:**

| Action | Description |
|--------|-------------|
| **Power On** | Start the selected VMware VM |
| **Power Off** | Stop the selected VMware VM |
| **Suspend** | Suspend the VM to disk |
| **Reset** | Force-restart the VM |
| **Snapshot** | Create a named snapshot (`snapshot_<timestamp>`) |

**VirtualBox Operations:**

| Action | Description |
|--------|-------------|
| **Start** | Start the selected VirtualBox VM |
| **Stop** | Power off the VM |
| **Pause** | Pause VM execution |
| **Reset** | Force-restart the VM |

**VM Table Columns (VMware):** Name, Guest OS, State, IP Address

**VM Table Columns (VirtualBox):** Name, OS Type, State, Memory

**Requirements:**
- VMware Workstation/Player or VirtualBox must be installed on the host
- The backend adapter connects via the respective hypervisor's API or CLI

---

## 6. VM Console Streaming

The **VM Console** panel provides a live view of the VM display through the Continuum Streaming Bridge.

**Screenshot Description:** *The VM Console panel shows a connection status card with a "WebSocket" indicator and Connect/Disconnect buttons. Below is a large QGraphicsView rendering the live VM display as JPEG frames. At the bottom, status text shows frame count, bytes received, and current resolution (e.g., "Frames: 1250 | 2.4 MB | 1920x1080").*

**How It Works:**

1. The **Streaming Bridge** (`streaming_bridge.py`) runs as a service on `ws://127.0.0.1:8445/ws/stream`
2. It captures desktop/VM frames via Continuum's native capture at up to 60 FPS
3. Frames are encoded as JPEG (default quality: 85) and broadcast to connected WebSocket clients
4. The VM Console panel connects and renders each frame in a QGraphicsView

**Connecting:**

1. Open the **VM Console** panel
2. Click **Connect** -- establishes WebSocket connection to `ws://127.0.0.1:8445/ws/stream`
3. The VM display appears in the view area
4. Click **Disconnect** to stop streaming

**Streaming Protocol:**

| Message Type | Direction | Description |
|-------------|-----------|-------------|
| JPEG frame | Server -> Client | Binary frame data (continuous stream) |
| `{"type":"config","quality":85}` | Client -> Server | Adjust JPEG quality (1-100) |
| `{"type":"ping","time":<ms>}` | Client -> Server | Latency measurement |
| `{"type":"input","input_type":...}` | Client -> Server | Forward input events to VM |
| `{"type":"stats_request"}` | Client -> Server | Request streaming statistics |

**Starting the Bridge Manually:**

```bash
python streaming_bridge.py
```

The bridge listens on `0.0.0.0:8445` and accepts WebSocket connections. It supports multiple simultaneous clients and includes Docker exec subprocess pooling for terminal access.

**Display Configuration:**

| Setting | Default | Description |
|---------|---------|-------------|
| Capture FPS | 60 | Frames per second |
| JPEG Quality | 85 | Compression quality (1-100) |
| Max Resolution | 1920x1080 | Upper bound for frame dimensions |
| WebSocket Host | 0.0.0.0 | Bind address |
| WebSocket Port | 8445 | Listen port |

---

## 7. Image Pull Progress

When pulling Docker images, the **Image Pull Dialog** provides real-time progress feedback.

**Screenshot Description:** *The Image Pull Dialog is a modal QProgressDialog with the title "Pulling Image - ubuntu:22.04". It shows a label reading "Pulling 'ubuntu:22.04': Downloading [layer-id]" and a blue progress bar. Below the bar, transfer size information shows "45.2 MB / 72.8 MB". A Cancel button is at the bottom. On completion, a modal message box shows "Image 'ubuntu:22.04' pulled successfully" (green info) or an error message (red critical).*

**Using Image Pull:**

1. Open the **Container** panel -> **Images** tab
2. Click **Pull Image**
3. Enter the image name (e.g., `ubuntu:22.04`, `nginx:latest`)
4. The Image Pull Dialog opens and begins pulling

**What the Dialog Shows:**

| Element | Description |
|---------|-------------|
| Progress Bar | Overall pull percentage (0-100%) |
| Status Label | Current action: "Downloading", "Extracting", "Pull complete" |
| Layer ID | Short identifier of the current layer being processed |
| Transfer Info | Bytes downloaded / total bytes (e.g., "45.2 MB / 72.8 MB") |
| Cancel Button | Cancels the pull (checked between stream chunks) |

**Technical Details:**

- The blocking `docker pull` call runs in a background `QThread` to keep the GUI responsive
- Docker's streamed JSON output is parsed per-layer: `progressDetail.total` and `progressDetail.current` are used to compute percentage
- Byte counts are formatted human-readable: B, KB, MB, GB
- The dialog uses the app's dark theme (background #0f172a, brand-colored progress bar chunk)

---

## 8. Settings & Configuration

The **Settings** panel provides a tabbed interface for all configuration options.

**Screenshot Description:** *The Settings panel shows a tabbed widget with tabs: QEMU, VM, Display, Acceleration, Network, Logging, Snapshots, and Auth. Each tab contains a Card with form fields. At the bottom are three buttons: "Save Settings" (green), "Reset to Defaults", and "Refresh from .env". A status label below shows the last save/refresh result (e.g., "Settings saved to .env" in green or "Failed to save" in red).*

### Settings Tabs

#### QEMU Tab

| Setting | Default | Description |
|---------|---------|-------------|
| QEMU Binary | `C:/Program Files/qemu/qemu-system-x86_64.exe` | Path to QEMU executable |
| Extra QEMU Args | `-machine q35,kernel_platform=` | Additional command-line arguments |

#### VM Tab

| Setting | Default | Description |
|---------|---------|-------------|
| VM Name | `omarchy-vm` | Name identifier for the VM |
| Disk Path | `C:/Users/Server/Virtual Machines/omarchy-vm/disk.qcow2` | Path to the qcow2 disk image |
| ISO Path | *(empty)* | Path to ISO for CD-ROM mounting |
| RAM (MB) | 16384 | Memory allocation (512 - 65536) |
| vCPUs | 8 | Number of virtual CPUs (1 - 128) |
| Hostname | `omarchy-vm` | Guest hostname |

#### Display Tab

| Setting | Default | Description |
|---------|---------|-------------|
| Display Type | SDL | SDL, GTK, VNC, Spice, or None |
| OpenGL | Enabled | Enable OpenGL acceleration (SDL/GTK only) |
| Auto-eject ISO | Enabled | Automatically eject CD-ROM after boot |

#### Acceleration Tab

| Mode | Description | Requirements |
|------|-------------|--------------|
| **WHPX** (default) | Windows Hypervisor Platform -- best performance | Windows 10/11 with WHPX enabled |
| **HAXM** | Intel Hardware Accelerator | Intel VT-x, HAXM driver installed |
| **TCG** | Software emulation -- very slow (10-100x) | None (always works) |

When TCG is selected, a warning appears: *"TCG mode uses software emulation only. The VM will be extremely slow (10-100x slower). Only use for debugging."*

#### Network Tab

| Setting | Default | Description |
|---------|---------|-------------|
| SSH Host | 127.0.0.1 | Host address for SSH connections |
| SSH Port | 2222 | Host port forwarded to guest SSH (port 22) |
| Guest Username | omarchyvm | Default SSH username |

#### Logging Tab

| Setting | Default | Description |
|---------|---------|-------------|
| Log Level | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| Log File | *(empty)* | Optional file path for log output |

#### Snapshots Tab

The Snapshots tab contains the Snapshot Scheduler settings widget:

| Setting | Default | Description |
|---------|---------|-------------|
| Enabled | Off | Turn automated snapshot scheduling on/off |
| Interval | 60 min | Time between automatic snapshots |
| Retention | 10 | Maximum number of snapshots to keep |
| Name Prefix | `auto-` | Prefix for auto-generated snapshot names |

#### Auth Tab

| Setting | Default | Description |
|---------|---------|-------------|
| Auth Method | api_key | `api_key`, `jwt`, or `none` (development only) |
| API Key | *(stored securely)* | Use the Security panel to manage |

### Saving Settings

1. Adjust settings in any tab
2. Click **Save Settings** -- validates all fields and writes to `.env`
3. If validation fails, a warning dialog lists all errors
4. On success: *"Settings have been saved to .env. Restart the server to apply changes."*

### Resetting to Defaults

Click **Reset to Defaults** to restore all fields to factory defaults (does not auto-save).

### Refreshing from .env

Click **Refresh from .env** to reload all fields from the current `.env` file, discarding any unsaved changes.

---

## 9. TLS/SSL Setup

VM-Harness supports TLS/SSL encryption for REST API and WebSocket connections.

### Self-Signed Certificate (Development)

The project includes pre-generated `cert.pem` and `key.pem` in the root directory for development use.

**To generate a new self-signed certificate:**

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/CN=127.0.0.1" \
  -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"
```

### Enabling TLS

In `.env`, configure the following:

```env
# TLS Configuration
TLS_ENABLED=true
TLS_CERT_PATH=cert.pem
TLS_KEY_PATH=key.pem
TLS_PORT=8443
```

**Configuration Options:**

| Variable | Default | Description |
|----------|---------|-------------|
| `TLS_ENABLED` | false | Enable TLS for API and WebSocket |
| `TLS_CERT_PATH` | cert.pem | Path to the SSL certificate file |
| `TLS_KEY_PATH` | key.pem | Path to the SSL private key file |
| `TLS_PORT` | 8443 | Port for HTTPS/WSS connections |

### Connecting with TLS

**REST API:**

```bash
curl -k https://127.0.0.1:8443/api/v1/status
```

The `-k` flag skips certificate verification (for self-signed certs). For production, use the certificate authority chain instead.

**WebSocket:**

```
wss://127.0.0.1:8445/ws/stream
```

**Python Client:**

```python
import ssl
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE  # For self-signed certs only

req = urllib.request.Request("https://127.0.0.1:8443/api/v1/status")
with urllib.request.urlopen(req, context=ctx) as resp:
    print(resp.read().decode())
```

### Production TLS

For production deployments:

1. **Obtain a certificate** from a trusted CA (Let's Encrypt, DigiCert, etc.)
2. **Set the paths** in `.env`:
   ```env
   TLS_CERT_PATH=/etc/letsencrypt/live/your-domain.com/fullchain.pem
   TLS_KEY_PATH=/etc/letsencrypt/live/your-domain.com/privkey.pem
   ```
3. **Use a reverse proxy** (nginx, Caddy) for automatic certificate renewal
4. **Enable HSTS** headers if using a reverse proxy

### Security Best Practices

- Never commit `cert.pem` and `key.pem` to version control (they are in `.gitignore`)
- Use 4096-bit RSA keys for production
- Rotate certificates before expiration
- Never use self-signed certificates in production
- The Container Logs dialog uses `ssl._create_unverified_context()` by default -- replace with proper verification in production

---

## 10. Troubleshooting

### QEMU Not Found

**Symptoms:** "QEMU binary not found" error; VM status shows "Stopped" immediately.

**Solutions:**

1. Verify QEMU is installed: `qemu-system-x86_64 --version`
2. Fix the path in **Settings > QEMU > QEMU Binary**
3. Common Windows paths: `C:/Program Files/qemu/qemu-system-x86_64.exe`
4. Add QEMU's directory to system PATH and restart

### SSH Connection Failures

**Symptoms:** "Connection refused" when connecting to guest; Guest Terminal shows disconnected.

**Solutions:**

1. Verify VM is running (Dashboard status = green)
2. Check SSH port forwarding: `netstat -an | findstr 2222` (Windows)
3. Verify SSH server is running in the guest: `sudo systemctl status sshd`
4. Install SSH server if missing:
   ```bash
   sudo apt install openssh-server
   sudo systemctl enable --now sshd
   ```
5. Test manually: `ssh -p 2222 omarchyvm@127.0.0.1`
6. Check credentials in **Settings > Network**

### QMP Connection Failures

**Symptoms:** "QMP disconnected" error; VM control operations fail.

**Solutions:**

1. Check QMP settings in `.env`: `QMP_HOST=127.0.0.1`, `QMP_PORT=4444`
2. Verify QEMU was started with QMP: `-qmp tcp:127.0.0.1:4444,server,nowait`
3. Check if QEMU process is running: `tasklist | findstr qemu`
4. Test connectivity: `telnet 127.0.0.1 4444`
5. Check Windows Firewall rules for port 4444

### VM Won't Start

**Solutions:**

1. Check disk image exists: verify path in **Settings > VM > Disk Path**
2. Run disk check: `qemu-img check <disk-path>`
3. Validate RAM (256 MB - 131072 MB) and CPU (1 - 128) values
4. Check for port conflicts on 2222 and 4444
5. Run QEMU manually to see error output:
   ```bash
   qemu-system-x86_64 -drive file=<disk>,format=qcow2 -m 8192 -smp 4 -display sdl
   ```

### Display Issues

**Symptoms:** No display window; blank/black screen; VNC connection fails.

**Solutions:**

| Display Type | Solution |
|-------------|----------|
| **SDL/GTK** | Ensure QEMU binary supports the selected backend; check SDL libraries |
| **VNC** | Connect with VNC client to `127.0.0.1:5900` |
| **Spice** | Install SPICE client (virt-viewer); connect to port 5930 |
| **None** | VM runs headless -- use SSH or VNC for access |

### Container Issues

**Symptoms:** Docker backend shows red indicator; container list empty.

**Solutions:**

1. Verify Docker is installed and running: `docker version`
2. Check Docker socket access (Linux: `/var/run/docker.sock`)
3. Verify the async adapter can reach the Docker API
4. Check that the VM (if running Docker inside VM) is up
5. For Kubernetes: verify `kubectl` is configured and cluster is reachable

### Performance Issues

**Solutions:**

1. Use hardware acceleration (WHPX or HAXM) -- see **Settings > Acceleration**
2. Allocate adequate RAM (minimum 2 GB for modern OS)
3. Use qcow2 disk format with appropriate cache mode
4. Enable OpenGL for graphics acceleration
5. Reduce vCPU count if host is overloaded
6. Monitor with **Telemetry** and **Monitoring** panels

### Collecting Diagnostic Information

When reporting issues, include:

1. VM-Harness version
2. Python version (`python --version`)
3. QEMU version (`qemu-system-x86_64 --version`)
4. OS and version
5. Error messages from Logs panel or terminal
6. `.env` settings (remove sensitive values)
7. QEMU command line being used

### Quick Error Reference

| Error | Likely Cause | Solution |
|-------|--------------|----------|
| "QEMU binary not found" | Wrong path or QEMU not installed | Fix path in Settings or install QEMU |
| "Connection refused" (SSH) | SSH server not running in guest | Install SSH server in guest |
| "QMP disconnected" | QMP socket unavailable | Restart VM, check QMP settings |
| "Could not set up host forwarding" | Port conflict | Use different SSH port |
| "VM not running" | VM is stopped | Start the VM first |
| "Disk not found" | Wrong disk path | Update disk path in Settings |
| "Display initialization failed" | Display backend issue | Try different display type |

---

## CLI Reference

```bash
# System status
qemu-mcp status

# VM lifecycle
qemu-mcp vm list
qemu-mcp vm start <name>
qemu-mcp vm stop <name>
qemu-mcp vm restart <name>

# Snapshots
qemu-mcp snapshot list
qemu-mcp snapshot create <name>

# ISOs
qemu-mcp iso list

# Configuration
qemu-mcp config get

# REST API
qemu-mcp api start --port 8080

# Launch GUI
qemu-mcp gui
```

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/status` | System status |
| GET | `/api/v1/vms` | List VMs |
| GET | `/api/v1/config` | Get configuration |
| GET | `/api/v1/isos` | List ISOs |
| GET | `/api/v1/containers` | List containers |
| GET | `/api/v1/containers/<name>/logs?tail=<N>` | Container logs |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Tab` | Cycle through panels |
| `Ctrl+1` through `Ctrl+9` | Jump to specific panel |
| `F5` | Refresh current panel |
| `Ctrl+Q` | Quit application |

---

*Documentation version: 2.0.0 | VM-Harness v2.0.0*
*Developed by Omarchy VM Control | Released under MIT License*

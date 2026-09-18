# QEMU-MCP Agent Guide

**For AI agents that connect to this MCP server.**

QEMU-MCP exposes 13 tools over MCP's stdio transport (default) or streamable HTTP.
Agents interact with VMs through these tools — never through raw QMP/SSH.

---

## Security model

- **Credentials are never exposed to agents.** SSH passwords, API keys, QMP passwords,
  and private keys live in the server's `Secrets` object (memory only) and are injected
  server-side. Tool results and error messages contain no credential data.
- **The GUI credential store** (`~/.local/share/qmcmcp/credentials.json`) is optional
  and uses Fernet symmetric encryption. Agents do NOT access it — only the GUI does.
- **Authentication** (when enabled via `AUTH_ENABLED=true`) requires clients to present
  `Authorization: Bearer <AUTH_API_KEY>` on every MCP connection.

---

## Tool reference

### VM Lifecycle (8 tools)

| Tool | Description | Required params | Optional params |
|---|---|---|---|
| `vm_status` | Get current VM status (state, PID, RAM, vCPUs) | — | — |
| `vm_start` | Start the VM using configured QEMU binary + args | — | `vm_name`, `ram_mb`, `cpus`, `disk_path`, `iso_path`, `display`, `gl` |
| `vm_stop` | Graceful shutdown via QMP `system_powerdown` | — | — |
| `vm_reset` | Hard reset via QMP `system_reset` | — | — |
| `vm_suspend` | Suspend VM to RAM via QMP `stop` | — | — |
| `vm_resume` | Resume suspended VM via QMP `cont` | — | — |
| `vm_eject_cdrom` | Eject the ISO from virtual CDROM | — | `vm_name` |
| `vm_boot_device` | Get or set boot order (disk/cdrom/net) | — | `boot_index`, `device`, `on_catalog` |

**Pattern:** `vm_start` → wait for QMP status "running" → use guest tools → `vm_stop`.

### Guest Operations (5 tools)

These require the VM to be running **and** SSH to be accessible (default: port 2222,
username `OmarchyVM`). SSH credentials come from `.env` (`SSH_USERNAME` + `SSH_PASSWORD`
or `SSH_PRIVATE_KEY`).

| Tool | Description | Required params | Optional params |
|---|---|---|---|
| `guest_exec` | Execute a shell command inside the guest | `command` | `timeout_sec`, `vm_name` |
| `guest_file_read` | Read a text file from guest filesystem | `path` | `max_bytes` (default 1 MiB), `vm_name` |
| `guest_file_write` | Write content to a file in guest | `path`, `content` | `vm_name` |
| `guest_file_list` | List directory contents (recursive optional) | `path` | `recursive` (default False), `vm_name` |
| `guest_file_remove` | Remove a file or directory | `path` | `recursive` (default False), `vm_name` |

**Required params are marked in each tool's input schema.** Agents should inspect the
schema via `list_tools()` before calling.

---

## Typical workflows

### 1. Start a VM and run a command

```
1. vm_start()                    # uses defaults from .env
2. loop: vm_status()             # wait until state == "running"
3. guest_exec(command="uname -a")
4. guest_exec(command="df -h /")
5. vm_stop()                     # graceful shutdown
```

### 2. Inspect a file in the guest

```
1. vm_status()                   # confirm running
2. guest_file_list(path="/etc/os-release")
3. guest_file_read(path="/etc/os-release")
```

### 3. Deploy a config file

```
1. vm_status()
2. guest_file_write(
       path="/etc/myapp/config.yaml",
       content="server:\n  port: 8080\n"
   )
3. guest_exec(command="cat /etc/myapp/config.yaml")
```

### 4. Clean up a directory

```
1. guest_file_list(path="/tmp/build", recursive=True)
2. guest_file_remove(path="/tmp/build", recursive=True)
3. guest_file_list(path="/tmp")   # verify
```

---

## Error handling

- **VM not running:** `guest_exec`, `guest_file_*` will fail. Call `vm_status` first.
- **SSH unreachable:** Guest tools fail with a connection error. Verify the VM is running
  and port forwarding is active (`-netdev user,hostfwd=tcp::2222-:22`).
- **QMP disconnected:** VM lifecycle tools (start/stop/reset/etc.) depend on QMP. If QMP
  is not available, these fail. Start the VM first or check QMP_HOST/QMP_PORT in `.env`.
- **Tool schema errors:** If you pass a parameter not in the schema, the server returns
  a validation error. Use `list_tools()` to get current schemas.

---

## Discovery

Call `list_tools()` to get the full list of tool names, descriptions, and input schemas.
Schemas are JSON Schema — they tell you exactly which parameters are required and what types
they accept.

Example schema excerpt for `guest_exec`:
```json
{
  "type": "object",
  "properties": {
    "command": { "type": "string" },
    "timeout_sec": { "type": "integer", "default": 30 },
    "vm_name": { "type": "string" }
  },
  "required": ["command"]
}
```

---

## Transport

- **stdio (default):** The server reads/writes JSON-RPC on stdin/stdout. Use when the MCP
  client is a local process (e.g. an IDE plugin, a terminal harness).
- **streamable HTTP:** Set `TRANSPORT=sse` in `.env` and launch with `vm-mcp --transport sse`.
  Agents connect via HTTP POST to `http://<SSE_HOST>:<SSE_PORT>/`.

---

## Settings

All settings come from `.env` (or the path in `VM_MCP_ENV_FILE`). The GUI Settings panel
writes changes back to `.env`. Key settings:

| Setting | Default | Meaning |
|---|---|---|
| `QMP_HOST` | `127.0.0.1` | QMP TCP host |
| `QMP_PORT` | `4444` | QMP TCP port |
| `SSH_HOST` | `127.0.0.1` | SSH guest host (QEMU user-mode NAT) |
| `SSH_PORT` | `2222` | SSH guest port |
| `SSH_USERNAME` | `OmarchyVM` | SSH login username |
| `SSH_PASSWORD` | (none) | SSH password (or use `SSH_PRIVATE_KEY`) |
| `SSH_PRIVATE_KEY` | (none) | Path to SSH private key |
| `QEMU_BINARY` | `qemu-system-x86_64` | QEMU executable |
| `VM_DISK_PATH` | (none) | Path to VM disk image |
| `VM_ISO_PATH` | (none) | Path to install ISO |
| `VM_RAM_MB` | `8192` | VM RAM in MB |
| `VM_CPUS` | `4` | VM vCPUs |
| `VM_DISPLAY` | `sdl` | QEMU display backend |
| `VM_GL` | `true` | Enable OpenGL |
| `VM_NAME` | `omarchy-vm` | VM identifier |
| `AUTO_EJECT_ISO` | `true` | Auto-eject ISO on boot |

---

## Extensibility

QEMU-MCP is built on an `Extension` class hierarchy. New VM types, new transports, and new
tool sets can be added by subclassing `Extension` and registering with `MCPServer`. The
architecture is designed for 100-year evolution: swap out QEMU for another hypervisor,
add new guest OS support, or add new transport protocols without rewriting the server core.

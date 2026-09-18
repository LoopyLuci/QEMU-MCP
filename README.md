# vm-mcp — Secure MCP server for QEMU/Omarchy VM control

Control a QEMU virtual machine running Omarchy Linux through the Model
Context Protocol (MCP).  AI agents get tools to manage the VM lifecycle,
run commands inside the guest, transfer files, and inspect state — without
ever seeing passwords, SSH keys, or QMP credentials.

Built for 100-year longevity: async throughout, Pydantic-validated
boundaries, three-layer secret isolation, protocol-agnostic transports,
and swappable tool modules.

## Quick start

```bash
# 1. Configure
cp .env.example .env   # edit with your values

# 2. Install
pip install -e ".[dev]"

# 3. Run (stdio transport — for local MCP clients like Hermes)
vm-mcp

# Or SSE transport (for remote agents)
python -m vm_mcp --transport sse --host 0.0.0.0 --port 8080
```

## Architecture

```
  MCP Client (agent)          vm-mcp Server          QEMU / Guest
  ──────────────────          ───────────────        ─────────────
       │                          │                      │
       │  MCP call/read/          │                      │
       │  subscribe               │                      │
       │  ──────────────────────► │                      │
       │                          │  ┌─────────────────┐ │
       │                          │  │   Tool layer    │ │
       │                          │  │   (validated    │ │
       │                          │  │    params,      │ │
       │                          │  │    no secrets   │ │
       │                          │  │    exposed)     │ │
       │                          │  └───────┬─────────┘ │
       │                          │          │            │
       │                          │  ┌───────▼─────────┐ │
       │                          │  │  QMP client     │ │
       │                          │  │  (TCP/Unix      │ │
       │                          │  │   socket)       │ │
       │                          │  └───────┬─────────┘ │
       │  Tool result ◄───────────│          │            │
       │                          │          ▼            │
       │                          │  QEMU process         │
       │                          │  (running on host)    │
       │                          │                      │
       │                          │  ┌─────────────────┐ │
       │                          │  │  SSH client     │ │
       │                          │  │  (asyncssh)     │ │
       │                          │  └───────┬─────────┘ │
       │  File/content ◄──────────│          │            │
       │                          │          ▼            │
       │                          │  Guest OS             │
       │                          │  (Omarchy/Hyprland)   │
       │                          │                      │
       │  Resource read ◄─────────│                      │
       │  (VM state, logs,        │                      │
       │   config summary)        │                      │
       │                          │                      │
```

## Secret isolation (three layers)

| Layer | What it holds | Who sees it |
|-------|---------------|-------------|
| `.env` file | SSH password, QMP password, API keys, JWT secret | Only the file owner (chmod 600) |
| `Secrets` object | In-memory copy of .env values | Server internals only; never serialized or logged |
| Tool functions | Receive necessary values through dependency injection | Caller (agent) never sees the raw secret, only the tool's output |

## Tool overview

### VM Lifecycle
| Tool | Description |
|------|-------------|
| `vm_status` | VM state: running/stopped, PID, uptime, memory, CPU |
| `vm_start` | Start the VM (QEMU with QMP control socket) |
| `vm_stop` | Graceful shutdown (QMP system_powerdown) |
| `vm_reset` | Hard reset (QMP system_reset) |
| `vm_suspend` | Suspend-to-RAM (QMP stop) |
| `vm_resume` | Resume from suspend (QMP cont) |
| `vm_eject_cdrom` | Eject the installation ISO after install completes |
| `vm_boot_device` | Query or set boot order (disk, cdrom, network) |

### Guest Interaction (requires SSH)
| Tool | Description |
|------|-------------|
| `guest_exec` | Run a command inside the guest, return stdout/stderr/exit code |
| `guest_exec_stream` | Run a command with streaming output (for long-running commands) |
| `guest_file_read` | Read a file from the guest filesystem |
| `guest_file_write` | Write a file to the guest filesystem |
| `guest_file_list` | List files/directories in the guest |
| `guest_file_remove` | Remove a file or directory in the guest |

### Diagnostics
| Tool | Description |
|------|-------------|
| `vm_info` | Detailed QEMU info: machine type, firmware, devices, memory maps |
| `vm_block_info` | Disk and block device information |
| `vm_network_info` | Network device configuration |
| `guest_os_info` | Detect guest OS, kernel version, running services |
| `guest_disk_usage` | Disk space usage inside the guest |
| `guest_process_list` | List running processes in the guest |
| `vm_logs` | QEMU console output / serial log (if available) |

### Prompts (guided workflows)
| Prompt | Description |
|--------|-------------|
| `install_guide` | Step-by-step Omarchy installation via cidata unattended install |
| `troubleshoot_boot` | Diagnose boot failures, check serial console, verify boot device |
| `post_install_setup` | Enable SSH, create user, configure tailscale, set up development tools |

## Configuration (.env)

Copy `.env.example` to `.env` and fill in your values.  All fields have
defaults so you can run without a `.env` for testing.

```ini
# Required for guest interaction
SSH_PASSWORD=YourVMPasswordHere
# OR use key-based auth:
SSH_PRIVATE_KEY=/path/to/private/key

# QMP connection (usually auto-detected from VM config)
# QMP_PASSWORD=optional-if-qemu-uses-password-auth

# Server security
AUTH_ENABLED=false
AUTH_API_KEY=your-secret-api-key-here
```

## Security

- **Secrets never leave the server**: Tools call internal functions that use
  secrets; the raw values are never included in tool results or logs.
- **Pydantic validation on every tool parameter**: Type errors and missing
  required fields are rejected before any I/O happens.
- **SSH host key verification**: When `SSH_KNOWN_HOSTS` is set, connections
  verify the guest's host key.  For local VMs, leave it unset (with the
  understanding that this trusts the local hypervisor).
- **QMP authentication**: When `QMP_PASSWORD` is set, the QMP client
  authenticates before issuing commands.
- **Auth middleware**: When `AUTH_ENABLED=true`, all MCP connections require
  an API key (passed as `Authorization: Bearer <key>` header in SSE mode,
  or as a custom header in other transports).

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with a specific transport
python -m vm_mcp --transport stdio

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/ tests/
```

## File layout

```
vm-mcp/
├── pyproject.toml              # Project metadata, dependencies, tool config
├── README.md                   # This file
├── .env.example                # Example environment configuration
├── .gitignore
├── src/
│   └── vm_mcp/
│       ├── __init__.py         # Package metadata (version)
│       ├── main.py             # CLI entry point + MCP server bootstrap
│       ├── config.py           # Pydantic Settings + Secrets classes
│       ├── setup.py            # QEMU process setup and launch
│       ├── qmp_client.py       # QMP protocol client
│       ├── ssh_client.py       # AsyncSSH client wrapper
│       ├── logging_setup.py    # Logging configuration
│       ├── tools/
│       │   ├── __init__.py     # Tool registry and re-exports
│       │   ├── _base.py        # Base classes and helpers
│       │   ├── vm_lifecycle.py # VM start/stop/reset/eject tools
│       │   ├── vm_status.py    # VM state query tools
│       │   ├── guest_exec.py   # Command execution in guest
│       │   ├── guest_files.py  # File operations in guest
│       │   └── diagnostics.py  # VM and guest diagnostics
│       ├── resources.py        # MCP resources (read-only state)
│       ├── prompts.py          # MCP prompts (guided workflows)
│       └── skills/             # Built-in skills for agents
│           └── README.md       # How agents should use vm-mcp
└── tests/
    ├── __init__.py
    ├── conftest.py             # Shared test fixtures
    ├── test_config.py          # Settings and Secrets tests
    ├── test_setup.py           # VM setup/launch tests
    └── test_tools.py           # Tool integration tests
```

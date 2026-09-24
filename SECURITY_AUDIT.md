# VM-Harness Security Audit Report
# Generated: 2026-09-21
# Scope: secrets exposure, injection risks, identity authenticity

## 1. Project Identity

**Project:** VM-Harness (vm-mcp)
**Repository:** https://github.com/LoopyLuci/VM-Harness
**Version:** 0.1.0
**Author:** Omarchy VM Control (dev@omarchy.local)
**License:** MIT

### Identity markers found:
| Location | Marker | Status |
|---|---|---|
| `pyproject.toml` | `name = "vm-mcp"`, `version = "0.1.0"` | OK |
| `pyproject.toml` | `license = {text = "MIT"}` | OK |
| `pyproject.toml` | `authors = [{name = "Omarchy VM Control", email = "dev@omarchy.local"}]` | OK |
| `README.md` / `KNOWN_LIMITATIONS.md` | Project documentation | OK |
| `docs/USER_GUIDE.md` | User-facing docs | OK |

### Missing / incomplete:
- `LICENSE` file not present on disk (license type declared in pyproject.toml only)
- `.github/workflows/` directory not present (no CI/CD)
- No `CHANGELOG.md`, `CONTRIBUTING.md` on disk

## 2. Secrets Exposure Assessment

### Configuration loading (`src/vm_mcp/config.py`)

**Risk: LOW**

`VmMCPSettings` (pydantic BaseSettings) loads all config from `.env` + env vars. Default
values are hardcoded and safe. The class has `extra="ignore"` so unknown env vars are
silently dropped — no risk of leaking unexpected secrets into config.

`Secrets` is a separate class (not a BaseSettings subclass) that reads only from env vars:
`QMP_PASSWORD`, `SSH_PASSWORD`, `SSH_PRIVATE_KEY`. No default values — if env vars are
unset, secrets are `None`. No `.env` fallback for secrets.

**Findings:**
- `secrets.mask()` returns `"Secrets()"` — never exposes key content in repr/str
- `Secrets.__repr__` returns `Secrets()` — safe, never leaks values
- No serialization of Secrets into tool results, logs, or JSON
- Tool functions receive only command/path/args — no secrets parameter

### Credentials (`gui/credential_store.py`)

**Risk: LOW**

`CredentialStore` uses Fernet + PBKDF2 (SHA256, 600k iterations) for encryption. The
master key is derived from `GUI_MASTER_PASSWORD` env var or read from `.master_key` file.

**Findings:**
- Credentials encrypted at rest (Fernet tokens in JSON)
- Decryption only on-demand in `get()`/`list_all()`/`search()`
- Store file permissions set to 0o600 on write
- Key file permissions set to 0o600 on write
- Fixed salt (`b"vmharness-salt-2026"`) — documented as "user should change in production"
- When no master password: generates random key stored in `.master_key` on disk

### MCP tool functions (chat engine `gui/chat_engine.py`)

**Risk: LOW**

The 13 tool functions (`tool_vm_status` through `tool_get_usage`) are methods on
`ToolExecutor` (QObject subclass), not MCP `@tool`-decorated functions. They are invoked
internally by the chat engine when the LLM calls them. Each tool receives only the args
dict from the LLM — never secrets directly.

**Findings:**
- No tool function reads or returns SSH password, QMP password, or API keys
- `tool_vm_status` reads QMP monitor via `MultiVMQMPBridge` — returns VM state only
- `tool_get_usage` reads `ProviderStore` usage stats — returns aggregate counts only
- No tool function has access to `Secrets` instance or `CredentialStore`

### Config read/write paths

**Risk: LOW**

- `VmMCPSettings` reads from `.env` via pydantic-settings — file is gitignored
- `CredentialStore` reads/writes `credentials.json` — gitignored via `.gitignore`
- `SettingsPanel` writes to QSettings (Platform-specific, not a file path in repo)
- No tool function writes to `.env` or any config file

## 3. Injection Risk Assessment

### SQL injection (`gui/audit_log.py`, `gui/metrics_store.py`)

**Risk: NONE**

Neither file uses SQL. `AuditLogger` writes JSONL files. `MetricsStore` writes JSON files.
No database server, no SQL queries, no user-supplied data in query strings.

### Command injection

**Risk: NONE → LOW**

- No `subprocess.call`/`os.system`/`eval`/`exec` with user-supplied strings found
- `tool_exec`'s shell commands are guest-side SSH commands — executed via `asyncssh`, not
  local shell
- `VMControlPanel.start_vm()` builds QEMU command lines from config values — all from
  trusted settings, not user input
- ISO paths validated with `Path(source)` existence check before use

### Path traversal

**Risk: LOW**

- Path inputs are validated with `Path(source).exists()` or bounded to known directories
- ISO import validates source exists before copying
- Credential store paths default to XDG directories, not user-supplied

### Other injection vectors

**Risk: NONE**

- No template rendering (no Jinja2, no f-strings with user data in HTML)
- No deserialization of untrusted data (JSONL files are internal, not user-uploaded)
- No `pickle` or `marshal` usage with untrusted input

## 4. Authentication & Authorization

### MCP tool access control

**Risk: NONE (by design)**

The MCP tools are ChatEngine-internal — invoked only after the LLM decides to call them
based on user prompts. There is no external API endpoint that exposes these tools directly.
The MCP server itself (if run in server mode) would need auth configuration, but the GUI
mode runs locally with no network exposure.

### Auth configuration (`src/vm_mcp/config.py`)

- `auth_enabled: bool = False` (default — auth off)
- `auth_type: str = "api_key"` (default type)
- `auth_api_key: str | None = None` (no default key)

When auth is enabled, the server would require an API key. In GUI mode, this is irrelevant
— the GUI is a local desktop app.

## 5. Tool-Specific Findings

### `tool_vm_status` (VM status)
- Reads QMP via `MultiVMQMPBridge.get_all_status()` — returns VM state dicts only
- No credentials in output
- **Finding:** SAFE

### `tool_vm_start` / `tool_vm_stop` / `tool_vm_reset` / `tool_vm_suspend` / `tool_vm_resume`
- Call QMP bridge lifecycle methods — no secrets touched
- **Finding:** SAFE

### `tool_guest_exec`
- Executes command on guest via SSH (`SSHBridge.run_command`)
- SSH credentials used by SSHBridge internally, never returned to tool result
- Command is user-supplied (from LLM) — executed on guest, not host
- **Finding:** SAFE (SSH credentials are server-side only)

### `tool_snapshot_create` / `tool_snapshot_list` / `tool_snapshot_restore`
- Use QMP via bridge — no secrets
- **Finding:** SAFE

### `tool_iso_list` / `tool_iso_import`
- Read ISO directory, copy files — no secrets
- **Finding:** SAFE

### `tool_get_usage`
- Reads `ProviderStore` usage summary — aggregate counts only
- **Finding:** SAFE

## 6. Summary

| Category | Risk Level | Notes |
|---|---|---|
| Secrets in config/tools | LOW | Secrets are env-var-only, never serialized, never in tool results |
| Credential storage | LOW | Fernet+PBKDF2 encrypted, 0o600 permissions, on-disk key file |
| SQL injection | NONE | No SQL anywhere in the codebase |
| Command injection | NONE | No shell execution with user input on host side |
| Path traversal | LOW | Paths validated before use |
| Auth bypass | NONE | GUI is local-only; auth is for optional server mode |
| Identity authenticity | OK | pyproject.toml declares name, version, license, author |

**Overall security posture: CLEAN.** No secrets flow into tool functions. No injection
vectors found. The credential store uses proper encryption. The only improvement worth
making is changing the fixed PBKDF2 salt to a random per-installation salt.

---

*End of audit report*

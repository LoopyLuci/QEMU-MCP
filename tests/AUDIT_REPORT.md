# Test Suite Audit Report — C:/Projects/QEMU-MCP/tests/

## 1. Tests That Don't Actually Test Anything

| File | Line(s) | Issue |
|------|---------|-------|
| `test_all_panels.py` | 37–41 | Only calls `panel.hide()` and `panel.show()` — verifies no crash, but no functional check |
| `test_gui_comprehensive.py` | 142–146, 232–258, 267–276, 283–290, 297–305, 312–319 | Tests only check `isinstance`, `hasattr`, or `is not None` — no behavioral verification |
| `test_integration.py` | 1012–1013 | `test_enumerate_usb_devices_wmi_fallback` has no assertion (missing `assert` entirely) |
| `test_vm_console.py` | 55–57 | `test_qapplication_exists` only checks `QApplication.instance() is not None` — trivial |
| `test_panels_network_editor.py` | 376–384 | `test_diagram_paint_event` ends with `assert True` — always passes regardless of paint result |
| `test_gui_comprehensive.py` | 437–461 | Widget tests (`test_card_widget`, `test_status_indicator`, etc.) only assert `is not None` |
| `test_gui_comprehensive.py` | 467–488 | Cross-cutting tests only check `hasattr` and `is not None` |

## 2. Missing Assertions

| File | Line(s) | Issue |
|------|---------|-------|
| `test_integration.py` | 1924–1931 | **Indentation bug**: `assert "ollama" in summary["by_provider"]` is outside the `with` block. `summary` is undefined → `UnboundLocalError`. Same for lines 1925–1931 |
| `test_integrations.py` | 101–102, 109–111, 229–231, 249, 349–350, 384–385, 427–428, 477–478, 487–488 | Tests use bare `pass` in `except` blocks instead of `assert` or `self.fail()` — silently swallows failures |
| `test_integrations.py` | 55–56, 132–133, 247, 288–289, 401 | `cls.skipTest(cls, ...)` called inside `setUpClass` — incorrect API usage (should raise `unittest.SkipTest` or return early) |
| `test_integrations.py` | 385–387 | `self.skipTest("QEMU lifecycle test skipped: {e}")` — message formatting bug: `{}` not prefixed with `f` |
| `test_image_pull.py` | 66–126 | `test_pull_alpine_latest` has no assertion if all 3 attempts fail — just calls `self.fail()` but only after sleep delays |
| `test_ai_providers.py` | 177 | `asyncio.run(self._test_no_providers())` called from a synchronous test method — works but unconventional; should use `pytest.mark.asyncio` |

## 3. Hardcoded Values That May Break

| File | Line(s) | Issue |
|------|---------|-------|
| `test_gui.py` | 331 | `assert len(win.panels) == 25` — hardcoded panel count breaks when panels added/removed |
| `test_gui_comprehensive.py` | 124 | `assert len(main_window.panels) == 25` — same hardcoded count |
| `test_gui_comprehensive.py` | 128–135 | `expected` set has 25 panel names hardcoded — must be updated whenever sidebar changes |
| `test_performance.py` | 62 | `assertGreaterEqual(len(panel_names), 33)` — hardcoded minimum |
| `test_gui_performance.py` | 115–116 | `assertGreaterEqual(len(panel_names), 32)` — hardcoded minimum |
| `test_vm_console.py` | 152 | `assertEqual(self.panel._url_label.text(), "ws://127.0.0.1:8445/ws/stream")` — hardcoded URL/port |
| `test_core.py` | 173 | `settings.vm_iso_path = r"C:\test\omarchy.iso"` — Windows-specific path fails on Linux |
| `test_e2e_qmp_ssh.py` | 24, 52 | QMP port 4444 hardcoded — breaks if config changes |
| `test_terminal_e2e.py` | 53–54 | Bridge host/port hardcoded to `127.0.0.1:8445` |
| `test_gui.py` | 317 | `monkeypatch.setenv("QEMU_BINARY", str(Path(tmp) / "qemu.exe"))` — `.exe` extension is Windows-only |
| `test_ai_providers.py` | 169–172 | `_estimate_cost` test hardcodes OpenAI pricing constants — breaks if pricing table changes |

## 4. Tests That Skip Too Often

| File | Line(s) | Issue |
|------|---------|-------|
| `test_plugin_api.py` | 34 | Entire test class skipped when no plugins found — plugin tests never run in CI without plugins/ populated |
| `test_integrations.py` | 55–56, 132–133, 247, 288–289, 366, 401, 449 | Every integration test skips if backend unavailable — Docker/K8s/VMware/VirtualBox/QEMU/API tests almost always skip |
| `test_terminal_e2e.py` | 48 | Whole class skipped if Docker not available |
| `test_e2e_qmp_ssh.py` | 51–53, 73–75, 90–92, 108–110 | All QMP tests skip when QEMU not running — effectively dead tests in CI |
| `test_image_pull.py` | 66–126 | `test_pull_alpine_latest` requires live Docker daemon + network access — slow (60s timeout) and flaky |
| `test_panels_usb.py` | 459–460, 490–491, 512–513, 537–538, 707–708, 720–721, 750–751 | Tests use `pytest.skip()` inside conditional branches — silent passes that look like real tests |

## 5. Missing Test Coverage for Critical Paths

| Area | What's Missing |
|------|----------------|
| **Authentication/Authorization** | No tests for credential encryption/decryption round-trip, master key derivation, or access control |
| **Error Handling** | No tests for SSH connection failures, QMP error responses, network timeouts, or invalid input validation |
| **Concurrency** | No tests for race conditions in ProviderStore, MetricsStore, or AuditLogger under parallel access |
| **Data Integrity** | No tests for database corruption recovery, migration rollback, or schema version conflicts |
| **Tool Execution** | `test_integration.py` tests `tool_vm_start` but not `tool_vm_stop` timeout, `tool_guest_exec` with invalid commands, or `tool_iso_import` with missing source |
| **Chat Engine** | No tests for actual LLM API call mocking, tool selection logic, or multi-turn conversation state |
| **Resilience** | `test_integrations.py` only instantiates `CrashHandler`, `AtomicState`, `ProcessGuardian` — no behavioral tests |
| **Persistence** | No tests for what happens when `snapshot_schedules.json` or `audit.db` is corrupted mid-write |
| **Memory/Resource Cleanup** | No tests for verifying `close()` methods actually release DB connections, threads, or file handles |

## 6. Fixture/Setup Issues

| File | Line(s) | Issue |
|------|---------|-------|
| `conftest.py` | 84–91 | Reloading 30+ modules after every test function is slow and can mask import-order bugs — only resets singletons, not other state |
| `test_ai_providers.py` | 30–45 | `setup_method` directly mutates `_ps_module.PROVIDER_STORE_FILE` and `_ps_module.MASTER_KEY_FILE` — race condition if tests run in parallel (pytest-xdist) |
| `test_integration.py` | 41–47 | `qapp` fixture doesn't use `qtbot` — may cause QWidget leaks or crashes |
| `test_integrations.py` | 55–56 | `cls.skipTest(cls, ...)` in `setUpClass` is incorrect — `skipTest` must be called from within a test method |
| `test_image_pull.py` | 66–126 | Retry loop with `time.sleep(1)` makes test slow and non-deterministic |
| `test_performance.py` | 49–148 | Uses `time.sleep(0.1)` for GC settling — unreliable on slow CI runners |
| `test_gui_performance.py` | 56–63 | `_force_gc_and_settle` uses `time.sleep(delay)` — same issue |
| `test_plugin_integration.py` | 140–145 | Patches module-level classes (`qmp_mod.QMPBridge`) — not thread-safe, can leak between tests if not restored properly |

## 7. Logic Errors / Tautologies

| File | Line(s) | Issue |
|------|---------|-------|
| `test_panels_network_editor.py` | 248 | `assert new_mac != old_mac or True` — always passes (tautology). Should be `assert new_mac != old_mac` or remove |
| `test_gui_performance.py` | 266–269 | Timer leak threshold is 50, but comment says "hundreds of new timers" — inconsistent messaging |
| `test_snapshot_scheduler.py` | 442 | `disk_path=""` in `SnapshotSchedule` constructor then `schedule.disk_path = ""` — redundant, confusing intent |
| `test_integration.py` | 710 | `old_time = now.replace(hour=now.hour - 25) if now.hour >= 25 else now` — condition `now.hour >= 25` is never true (hours 0–23), so `old_time` is always `now` |

## 8. Duplicate / Overlapping Tests

| Files | Overlap |
|-------|---------|
| `test_integration.py` + `test_ai_providers.py` | Both test `ProviderStore`, `get_enabled_providers`, `set_api_key`, `record_usage`, `get_usage_summary` |
| `test_gui.py` + `test_gui_comprehensive.py` | Both test panel instantiation, widget construction, bridge creation |
| `test_performance.py` + `test_gui_performance.py` | Both test panel switching performance, memory RSS, timer leaks — nearly identical implementations |
| `test_integration.py` + `test_iso_manager.py` | Both test ISO manager scanning, external sources |
| `test_audit_log.py` + `test_integration.py` (TestAuditLog) | Both test audit log logging/querying |

## 9. Style / Maintainability Issues

| File | Line(s) | Issue |
|------|---------|-------|
| `test_integrations.py` | 1–599 | Uses `unittest.TestCase` style but is named `test_integrations.py` (singular vs plural inconsistency) |
| `test_all_panels.py` | 16–73 | Not a pytest/unittest file — uses raw `main()` function; won't be collected by pytest by default |
| `test_core.py` | 36, 43, 50 | `monkeypatch` fixtures used but not imported (`pytest` imported, but `monkeypatch` is a fixture — must be in test method signature) |
| `test_image_pull.py` | 17 | Stray `n# Suppress CLI console windows on Windows` — typo (`n#` instead of `#`) |
| `test_integrations.py` | 13 | `CREATE_NO_WINDOW = 0x08000000` defined but never used |
| `test_terminal_e2e.py` | 17 | Same stray `CREATE_NO_WINDOW = 0x08000000` unused |

---

## Summary of Critical Bugs

1. **`test_integration.py:1924`** — Indentation bug causes `UnboundLocalError: summary` — test will always error, not fail silently
2. **`test_integrations.py:55-56`** — `cls.skipTest(cls, ...)` in `setUpClass` is incorrect — may not skip properly
3. **`test_integrations.py:385-387`** — Missing `f`-prefix on skip message — prints literal `"{e}"` instead of error
4. **`test_panels_network_editor.py:248`** — Tautological assertion always passes
5. **`test_integration.py:710`** — Impossible condition makes test logic dead code
6. **`test_ai_providers.py:177`** — `asyncio.run` inside sync test method — fragile pattern

## Recommendations

1. Fix the indentation bug in `test_integration.py:1924` immediately
2. Replace hardcoded panel counts with dynamic lookups or constants
3. Convert `test_all_panels.py` to proper pytest/unittest format
4. Consolidate duplicate performance tests into a single file
5. Add error-handling and negative-path tests for critical modules
6. Fix `cls.skipTest` usage in `test_integrations.py`
7. Remove tautological assertion in `test_panels_network_editor.py`
8. Add tests for `summary()` scope after the `with` block in provider e2e test

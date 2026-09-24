# VM-Harness Deprecation Policy

## Overview

This document defines how VM-Harness handles the retirement of outdated
features, MCP tool schemas, and configuration options.  The goal is to
give users clear advance notice and a predictable migration path, while
keeping the codebase maintainable for the long term.

## MCP Tool Schema Deprecation

### Versioning

Every MCP tool schema carries an optional `schema_version` field:

```json
{
  "name": "vm_start",
  "schema_version": "2026-09-01",
  "parameters": { ... }
}
```

When a tool's parameters change in a backward-incompatible way, the
schema version is bumped and the old version is marked deprecated.

### Deprecation Lifecycle

| Phase | Duration | What Happens |
|-------|----------|-------------|
| **Deprecation announced** | Immediately | The tool/schema is flagged `deprecated: true` in the tool list.  A `DeprecationWarning` is emitted at runtime.  Documentation is updated. |
| **Warning period** | 2 release cycles (≈ 6 months) | Both old and new schemas work.  Users see warnings in logs and tool results.  Migration guide is published. |
| **Removal** | After warning period | The old schema is removed.  Calls using the old schema return an error with a clear message pointing to the new schema. |

### Detection

When a deprecated schema version is used, the tool returns:

```json
{
  "success": false,
  "error": "Tool 'vm_start' schema version '2025-01-01' is deprecated.  Use schema version '2026-09-01'.  See https://github.com/LoopyLuci/VM-Harness/blob/main/docs/MIGRATION_GUIDE.md"
}
```

## Configuration Option Deprecation

Configuration options in `pyproject.toml` / `.env` follow the same lifecycle:

1. **Deprecated:** The option is still accepted but a warning is logged.
2. **Removed:** The option is no longer read; a clear error is raised if it's present in config.

Deprecated options are listed in this file and in the release notes.

## Code Deprecation

Internal APIs follow a simpler lifecycle:

1. **Deprecated:** Decorated with `warnings.warn("X is deprecated", DeprecationWarning)`.
2. **Removed:** After 2 release cycles, the deprecated code is deleted.

## Versioning

VM-Harness uses [Semantic Versioning](https://semver.org/):

- **MAJOR** — backward-incompatible changes to MCP tool schemas or config.
- **MINOR** — new features, backward-compatible.
- **PATCH** — bug fixes, backward-compatible.

The current version is defined in `pyproject.toml` and can be overridden
by a git tag at build time (see `scripts/version_from_git.py`).

## Migration Guides

When a major version introduces breaking changes, a migration guide is
published at `docs/MIGRATION_GUIDE.md` with side-by-side examples.

## Contact

For questions about deprecations, open an issue at:
https://github.com/LoopyLuci/VM-Harness/issues

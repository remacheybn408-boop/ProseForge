# Changelog

## Unreleased

## 1.5.0

- Added native runtime: `proseforge web` CLI entry (native profile, per-user data dirs, SQLite WAL, persisted master/jwt keys, same-origin SPA hosting).
- Added PyInstaller onedir native bundles with complete manifests (version, git SHA, Python 3.12, target, dependency hashes); Windows zip and Linux tarball builds.
- Added platform installers: Inno Setup script with per-user data preservation and backup-then-migrate upgrade flow, HKCU Run autostart scripts, deb/rpm build scripts with user-systemd unit, and signed macOS pkg scripts with LaunchAgent.
- Added real upgrade path: `proseforge upgrade` (lock, backup, migrate, doctor, rollback with integrity check, sanitized reports) and `proseforge upgrade --check` readiness probe.
- Hardened CLI: doctor infers native profile without server indicators and no longer crashes on Windows; corrupted backups fail cleanly without tracebacks.
- Fixed same-origin default for `PROSEFORGE_PUBLIC_URL` in native mode; fixed asyncpg-to-psycopg downgrade for alembic revision checks.
- CI: repaired Ruff gate, replaced compromised trivy-action with pinned digest container scan (CVE-2026-33634), fixed pnpm audit invocation, wired Playwright E2E job, and added three-OS test matrix.

## 1.1.0

- Added durable model usage records, token budgets, provider/model discovery, and bilingual Ink workspace views.
- Added production Compose overrides, secure session-cookie behavior, origin checks, and backup/restore operations guidance.

- Added authenticated React writing shell with project, outline, context and workflow flows.
- Added persistent outline/context models and migration repair for inconsistent installations.
- Added native Anthropic and Google Gemini provider adapters.
- Added Docker startup schema repair and Celery-backed application task queue.
- Added Docker-only regression, recovery, backup and security documentation.

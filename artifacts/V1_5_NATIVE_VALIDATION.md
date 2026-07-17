# V1.5 Native Validation

Status: **BLOCKED — release gate not green**

Repository SHA: `96656e1aff7aa9cbe732bb21c7b576528522ab4f`  
Execution date: 2026-07-18  
Local container runtime: Podman

## Evidence

| Area | Command/result | Exit |
|---|---|---:|
| lifecycle, scheduler, wiring, static Web API | Podman Python pytest, 8 passed | 0 |
| CLI doctor/backup and existing backup regression | Podman Python pytest, 12 passed | 0 |
| upgrade/rollback | Podman Python pytest, 5 passed | 0 |
| health/readiness/fault injection | Podman Python pytest, 4 passed | 0 |
| packaging tests | Podman Python pytest, 2 passed | 0 |
| native queue + SQLite bootstrap/repositories | Podman Python pytest with read-only mounted `aiosqlite` 0.22.1, 20 passed | 0 |
| frontend unit/component tests | Podman Vitest, 13 files / 22 tests passed | 0 |
| frontend production build | Podman Vite build to disposable output | 0 |
| Linux packaging smoke | Podman `scripts/build_native.sh --target linux --format tar.gz --skip-sign` | 0 |

## Blocking evidence

- Full Python matrix collected 631 tests but exceeded the 300-second gate timeout.
- Integration database tests require a PostgreSQL service at `postgres:5432`; the available Podman environment has no compose provider and DNS resolution fails. This is recorded as untested/blocked, not green.
- The checked-in test image omitted the declared `aiosqlite` dependency. The native queue/database slice was rerun with the existing project virtualenv package mounted read-only; the repository itself was not changed to bypass the dependency.
- Frontend `tsc --noEmit` could not be certified because the mounted frontend dependency tree lacks `@types/react`, `@types/react-dom`, and `@types/node`; Vite build and all Vitest tests pass.
- macOS package/signing and Windows installer execution were not run on their native operating systems. They remain NOT TESTED.

V1.5 is therefore not marked complete, not tagged, and not pushed as a release.

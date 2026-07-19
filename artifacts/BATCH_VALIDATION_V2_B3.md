# V2 B3 Batch Validation

Date: 2026-07-19

All commands ran through Podman Compose with the `compose.yaml` and `compose.test.yaml` stack.

| Check | Result |
| --- | --- |
| `pytest -q tests/api/test_reviews_revisions.py tests/integration/revision tests/migration` | 8 passed |
| `pytest -q tests/api` | 63 passed |
| `ruff check proseforge tests` | passed |
| web TypeScript + Vitest + production build | 30 test files / 90 tests passed; build passed |

The local Compose provider does not implement the plan's `--parallel 1` flag, so the equivalent serial `up -d --build postgres redis` command was used. Registry retries occurred during the frozen web dependency install; the completed run was green.

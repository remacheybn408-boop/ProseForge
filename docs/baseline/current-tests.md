# Current Test Baseline

- Revision: `f6183d17f9a3d46eb42c6ed3c8a6ae2e135dc6a5`
- All commands ran inside Docker Compose containers.
- Build: `docker compose -f compose.yaml -f compose.test.yaml build` — passed
- Legacy: `docker compose -f compose.yaml -f compose.test.yaml run --rm legacy-test` — 408 passed
- API: `docker compose -f compose.yaml -f compose.test.yaml run --rm api-test` — 531 passed, 1 skipped
- Contract: `docker compose -f compose.yaml -f compose.test.yaml run --rm contract-test` — 17 passed
- Migration: `docker compose -f compose.yaml -f compose.test.yaml run --rm migration-test` — 22 passed
- Recovery: `docker compose -f compose.yaml -f compose.test.yaml run --rm recovery-test` — 5 passed
- Web: `docker compose -f compose.yaml -f compose.test.yaml run --rm web-test` — 8 passed and Vite build passed
- JUnit artifacts: `artifacts/pytest.xml`, `artifacts/api-pytest.xml`, `artifacts/contract-pytest.xml`, `artifacts/migration-pytest.xml`, `artifacts/recovery-pytest.xml`

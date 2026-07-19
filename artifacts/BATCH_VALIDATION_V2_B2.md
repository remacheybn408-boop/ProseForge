# V2 Batch B2 Validation

Date: 2026-07-19

Scope: V2-004 model/reasoning and V2-005 structured Story Bible, trigger injection, Context Inspector.

## Podman environment

- Podman client: 6.0.1
- Compose services: postgres, redis, provider-mock

## Results

| Command | Result |
| --- | --- |
| `podman compose -f compose.yaml -f compose.test.yaml run --rm api-test pytest -q tests/api` | 53 passed |
| `podman compose -f compose.yaml -f compose.test.yaml run --rm api-test pytest -q tests/api/test_story_bible.py tests/integration/context/test_snapshot_pins_facts.py tests/unit/conversations/test_compile_chat_context.py tests/unit/story_bible/test_service.py` | 14 passed |
| `podman compose -f compose.yaml -f compose.test.yaml run --rm api-test ruff check proseforge tests` | passed |
| `podman compose -f compose.yaml -f compose.test.yaml run --rm web-test` | 25 files / 79 tests passed; TypeScript and production build passed |

Notes: test output includes existing Python deprecation and JWT key-length warnings. No test failures remained. Full Playwright is intentionally deferred to V2-010 per the V2 test policy.

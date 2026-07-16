# ProseForge Web v1 Codex Rules

1. Read `docs/plans/PROSEFORGE_WEB_V1_CODEX_PLAN.md` before changing code.
2. Execute tasks in numeric order.
3. Work only on branch `feat/web-v1`.
4. Use test-driven development: failing test, minimal implementation, passing test.
5. New application code imports only `proseforge.*`.
6. Only `proseforge/infrastructure/legacy_engine/` may import `src.*`.
7. API routes call application use cases; routes never query the database directly.
8. Provider adapters never import application services or repositories.
9. Redis is disposable; PostgreSQL and BlobStore are durable.
10. Do not delete legacy data during migration.
11. Do not hardcode a permanent model list.
12. Do not expose API keys, prompts, or full novel text in logs.
13. Do not claim completion until Docker unit, integration, E2E, recovery, and backup tests pass.
14. Commit after each completed task using the commit message specified in the plan.
15. Continue through the plan without asking for routine confirmation; stop only when a requirement is genuinely impossible or unsafe.

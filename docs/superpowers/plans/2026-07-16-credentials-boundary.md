# Credentials Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make authenticated credential replacement/deletion correct in the web settings flow and prove owner isolation for credentials and model profiles.

**Architecture:** Keep the existing API upsert/delete endpoints and repository owner predicates. Add small pure web state helpers plus a focused credential list component so SettingsView only coordinates server calls and feedback. Add Docker PostgreSQL integration tests for durable replacement and cross-owner boundaries.

**Tech Stack:** FastAPI, SQLAlchemy async repositories, PostgreSQL in Docker Compose, React, TypeScript, Vitest, Testing Library, Playwright.

## Global Constraints

- All tests run in Docker; do not invoke host Python or Node toolchains.
- New application code imports only `proseforge.*`; only `proseforge/infrastructure/legacy_engine/` may import `src.*`.
- Do not delete legacy data during migration; this task creates no migration.
- Do not expose API keys, prompts, or full novel text in logs.
- Routes use application/repository boundaries and preserve owner predicates.
- UI controls must have visible labels, keyboard focus, semantic status text, and touch targets of at least 44px.

---

### Task 1: Add failing web credential-state tests

**Files:**
- Create: `apps/web/src/features/providers/credentialState.test.ts`
- Create: `apps/web/src/features/providers/credentialState.ts`

**Interfaces:**
- Produces `upsertCredential(credentials, next)` and `removeCredential(credentials, credentialId)` for `Credential[]`.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { removeCredential, upsertCredential } from "./credentialState";

const configured = { id: "credential-1", provider: "openai", masked_key: "old****key" };

describe("credential state", () => {
  it("replaces an existing provider row without duplicating it", () => {
    expect(upsertCredential([configured], { id: "credential-1", provider: "openai", masked_key: "new****key" })).toEqual([
      { id: "credential-1", provider: "openai", masked_key: "new****key" },
    ]);
  });

  it("removes only the selected credential row", () => {
    expect(removeCredential([configured, { id: "credential-2", provider: "anthropic", masked_key: "configured" }], "credential-1")).toEqual([
      { id: "credential-2", provider: "anthropic", masked_key: "configured" },
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f compose.yaml -f compose.test.yaml run --rm web-test pnpm exec vitest run src/features/providers/credentialState.test.ts`

Expected: FAIL because `credentialState.ts` does not export the requested helpers.

- [ ] **Step 3: Write minimal implementation**

```ts
import type { Credential } from "../../lib/api/client";

export function upsertCredential(credentials: Credential[], next: Credential): Credential[] {
  const index = credentials.findIndex(item => item.id === next.id || item.provider === next.provider);
  if (index < 0) return [...credentials, next];
  return credentials.map((item, currentIndex) => currentIndex === index ? next : item);
}

export function removeCredential(credentials: Credential[], credentialId: string): Credential[] {
  return credentials.filter(item => item.id !== credentialId);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose -f compose.yaml -f compose.test.yaml run --rm web-test pnpm exec vitest run src/features/providers/credentialState.test.ts`

Expected: 2 tests passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/providers/credentialState.ts apps/web/src/features/providers/credentialState.test.ts
git commit -m "test: define credential list replacement behavior"
```

### Task 2: Wire delete, replacement feedback, and accessible UI

**Files:**
- Modify: `apps/web/src/lib/api/client.ts`
- Modify: `apps/web/src/lib/i18n.tsx`
- Modify: `apps/web/src/workspace.tsx`
- Modify: `apps/web/src/styles/views.css`
- Test: `apps/web/src/lib/api/client.test.ts`
- Test: `apps/web/e2e/ordinary-user-smoke.spec.ts`

**Interfaces:**
- Consumes `upsertCredential` and `removeCredential` from Task 1.
- Produces `deleteCredential(credentialId): Promise<void>` and localized remove/confirmation/success copy.

- [ ] **Step 1: Write the failing test**

Extend the API client test with:

```ts
it("deletes a credential by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
  const { deleteCredential } = await import("./client");
  await expect(deleteCredential("credential-1")).resolves.toBeUndefined();
  expect(fetchMock).toHaveBeenCalledWith("/api/v1/credentials/credential-1", expect.objectContaining({ method: "DELETE", credentials: "include" }));
});
```

Add an E2E assertion after saving the credential that replacing it keeps one configured row, then accept the confirmation dialog and click the visible remove control; expect the configured row to disappear and the localized success message to be visible.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f compose.yaml -f compose.test.yaml run --rm web-test pnpm exec vitest run src/lib/api/client.test.ts`

Expected: FAIL because `deleteCredential` is not exported; the E2E assertion is not yet runnable.

- [ ] **Step 3: Write minimal implementation**

Add `deleteCredential` to the API client, replace `setCredentials([...credentials, record])` with `setCredentials(current => upsertCredential(current, record))`, and add a visible remove button that calls `window.confirm`, `deleteCredential`, `removeCredential`, and an `aria-live="polite"` message. Add localized English/Chinese strings and semantic focus/touch styling using existing tokens.

- [ ] **Step 4: Run target and Web regression**

Run: `docker compose -f compose.yaml -f compose.test.yaml run --rm web-test`

Expected: typecheck, 13+ test files, and production build pass.

- [ ] **Step 5: Run real authenticated E2E**

Run: `docker compose -f compose.yaml -f compose.test.yaml run --rm e2e`

Expected: 6+ E2E tests pass, including replacement and deletion in the ordinary-user flow.

- [ ] **Step 6: Commit**

```bash
git diff --check
git add apps/web/src/lib/api/client.ts apps/web/src/lib/i18n.tsx apps/web/src/workspace.tsx apps/web/src/styles/views.css apps/web/src/lib/api/client.test.ts apps/web/e2e/ordinary-user-smoke.spec.ts
git commit -m "fix: make credential replacement and deletion visible"
```

### Task 3: Add Docker-backed owner-boundary evidence

**Files:**
- Create: `tests/integration/database/test_model_profile_boundaries.py`
- Create: `tests/api/test_credentials.py`
- Modify: `tests/integration/database/test_credentials_upsert.py`

**Interfaces:**
- Exercises existing repository methods and unauthenticated route contracts; no production API surface changes.

- [ ] **Step 1: Write boundary tests**

Add tests that create two owner IDs and assert `list_for_user`, `get_for_user`, and `delete_for_user` never cross owners; create two model profiles and assert `get_owned` returns `None` for the other owner. Add a route test asserting credential listing and deletion require authentication.

- [ ] **Step 2: Run targeted Docker tests**

Run: `docker compose -f compose.yaml -f compose.test.yaml run --rm api-test pytest -q tests/integration/database/test_credentials_upsert.py tests/integration/database/test_model_profile_boundaries.py tests/api/test_credentials.py`

Expected: tests pass against PostgreSQL; if a test exposes a boundary failure, fix only the smallest owner predicate and rerun the same command.

- [ ] **Step 3: Run full API regression and formatting**

Run: `docker compose -f compose.yaml -f compose.test.yaml run --rm api-test` followed by `git diff --check`.

Expected: full API suite passes with only the documented optional `chromadb` skip.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/database/test_credentials_upsert.py tests/integration/database/test_model_profile_boundaries.py tests/api/test_credentials.py
git commit -m "test: prove credential and model profile owner boundaries"
```

### Task 4: Update validation evidence

**Files:**
- Modify: `artifacts/GROK_FINAL_VALIDATION.md`

- [ ] **Step 1: Run required Docker gates**

Run the Docker Compose contract, API, contract, migration, recovery, web, E2E, startup, worker ping, fault-injection, and backup-restore commands required by `AGENTS.md` and record exit codes and counts.

- [ ] **Step 2: Update and self-review the report**

Record the pre-report Git SHA, exact commands, counts, authenticated paths, Redis fault transition, backup SHA/restore target, known limitations, and the still-missing Grok plan.

- [ ] **Step 3: Commit and push**

```bash
git diff --check
git add -f artifacts/GROK_FINAL_VALIDATION.md
git commit -m "docs: record credential boundary validation"
git push origin feat/grok-product-completion
git push origin feat/grok-product-completion:master
```

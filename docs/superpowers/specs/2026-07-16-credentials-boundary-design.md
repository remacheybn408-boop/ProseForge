# Credentials Boundary Design

## Goal

Make provider credential replacement and deletion correct and observable in the authenticated web settings flow, while proving that credentials and model profiles remain owner-scoped.

## Scope

- Saving a credential for an already configured provider keeps the server-returned credential ID and replaces the matching row in browser state.
- The settings page exposes a visible, keyboard-accessible remove action with confirmation, success feedback, and an inline live region.
- API client coverage includes the credential deletion request and the existing replacement request.
- Docker-backed integration coverage proves credential replacement remains one row for one owner, deletion cannot target another owner’s row, and model profiles cannot be listed or mutated across owners.

## Non-goals

- No plaintext credential, prompt, or novel content is logged or returned.
- No migration deletes or rewrites existing durable credential data.
- No provider catalog changes; the catalog is intentionally global while profiles and credentials are owner-scoped.
- No broad SettingsView rewrite beyond the small credential-list state helper/component needed for this behavior.

## Design

`saveCredential` continues to use the existing server upsert contract. A pure `upsertCredential` helper replaces a local row by its returned ID, or appends only when the provider is new. A pure `removeCredential` helper filters by ID. The settings view calls `deleteCredential` only after `window.confirm`, removes the row on HTTP 204, and announces the result with `aria-live="polite"`.

The API route remains owner-scoped through repository methods. Tests exercise the repository boundary against the Docker PostgreSQL fixture and assert that a different owner’s credential/profile is not visible or mutable. The existing route 401 contract remains unchanged.

## Accessibility and UX

- The remove control has a visible localized text label, not an icon-only affordance.
- Existing button tokens provide the minimum touch target and visible focus state; no raw color is added to the component.
- Confirmation, success, and failure text are announced through the existing form message live region.
- The secret input is cleared after save and never prefilled from server data.

## Verification

Each code task follows failing test, observed failure, minimal implementation, target pass, Docker full regression, `git diff --check`, and an independent commit. The final report records all Docker commands and known limitations.

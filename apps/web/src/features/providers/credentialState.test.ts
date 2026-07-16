import { describe, expect, it } from "vitest";
import { removeCredential, upsertCredential } from "./credentialState";

const configured = { id: "credential-1", provider: "openai", masked_key: "old****key" };

describe("credential state", () => {
  it("replaces an existing provider row without duplicating it", () => {
    expect(upsertCredential([configured], { id: "credential-1", provider: "openai", masked_key: "new****key" })).toEqual([
      { id: "credential-1", provider: "openai", masked_key: "new****key" },
    ]);
  });

  it("collapses stale duplicate rows for one provider", () => {
    expect(upsertCredential([
      configured,
      { id: "credential-legacy", provider: "openai", masked_key: "legacy****key" },
    ], { id: "credential-1", provider: "openai", masked_key: "new****key" })).toEqual([
      { id: "credential-1", provider: "openai", masked_key: "new****key" },
    ]);
  });

  it("removes only the selected credential row", () => {
    expect(removeCredential([configured, { id: "credential-2", provider: "anthropic", masked_key: "configured" }], "credential-1")).toEqual([
      { id: "credential-2", provider: "anthropic", masked_key: "configured" },
    ]);
  });
});

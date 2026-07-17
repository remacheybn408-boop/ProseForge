import { expect, test } from "@playwright/test";

test("workflow controls are protected until a session is established", async ({ request }) => {
  const response = await request.post("/api/v1/workflows/example/retry");
  expect(response.status()).toBe(401);
});

import { expect, test } from "@playwright/test";

test("token usage API is protected until a session is established", async ({ request }) => {
  const response = await request.get("/api/v1/usage/summary");
  expect(response.status()).toBe(401);
});

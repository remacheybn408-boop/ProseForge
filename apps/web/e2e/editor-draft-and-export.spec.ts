import { expect, test } from "@playwright/test";

test("export endpoint is protected until a session is established", async ({ request }) => {
  const response = await request.post("/api/v1/projects/example/exports", { data: { format: "md" } });
  expect(response.status()).toBe(401);
});

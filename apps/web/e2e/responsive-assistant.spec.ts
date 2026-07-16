import { expect, test } from "@playwright/test";

test("responsive app shell serves a healthy page", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const response = await page.goto("/");
  expect(response?.ok()).toBeTruthy();
});

import { expect, test } from "@playwright/test";

test("localization shell is served", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#root")).toBeVisible();
});

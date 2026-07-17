import AxeBuilder from "@axe-core/playwright";
import { expect, Page, test } from "@playwright/test";

async function assertAccessible(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  const blocking = result.violations.filter(item => item.impact === "critical" || item.impact === "serious");
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

test("ink workspace pages have no critical or serious axe violations", async ({ page }) => {
  const email = process.env.E2E_EMAIL ?? "v2-e2e-b074fc29@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Projects", exact: true }).click();
  await expect(page.locator("h2", { hasText: "Projects" })).toBeVisible();
  await assertAccessible(page);

  const open = page.getByRole("button", { name: "Open" }).first();
  if (await open.count()) await open.click();
  await expect(page.locator("textarea.editor")).toBeVisible();
  await assertAccessible(page);

  await page.getByRole("button", { name: "Workflow", exact: true }).click();
  await assertAccessible(page);
  await page.getByRole("button", { name: "Writing Studio" }).click();
  await page.getByRole("button", { name: "Export snapshot" }).click();
  await expect(page.getByRole("dialog", { name: "Export snapshot" })).toBeVisible();
  await assertAccessible(page);
});

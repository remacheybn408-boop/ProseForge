import { expect, test } from "@playwright/test";

test("ordinary user can reach the Docker-backed sign-in workspace", async ({ page, request }) => {
  const health = await request.get("/api/v1/health/live");
  expect(health.ok()).toBeTruthy();
  await expect(health.json()).resolves.toEqual({ status: "ok" });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /sign in to your writing space/i })).toBeVisible();
  await expect(page.getByLabel("Email")).toHaveAttribute("type", "email");
  await expect(page.getByLabel("Password")).toHaveAttribute("type", "password");

  await page.getByRole("button", { name: /first run/i }).click();
  await expect(page.getByRole("heading", { name: /create your owner account/i })).toBeVisible();
  await page.getByLabel("Email").fill("e2e@example.local");
  await page.getByLabel("Password").fill("not-submitted");
  await expect(page.getByRole("button", { name: "Create account" })).toBeEnabled();
});

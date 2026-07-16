import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";

test("authenticated studio keeps core controls usable at all baseline widths", async ({ page, request }) => {
  const email = process.env.E2E_EMAIL ?? "e2e@example.local";
  const password = process.env.E2E_PASSWORD ?? "E2ePassw0rd!";
  await request.post("/api/v1/auth/setup", { data: { email, password } });

  await page.goto("/");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.locator(".auth-card button.primary").click();
  await expect(page.getByRole("button", { name: "English", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "English", exact: true }).click();

  const projectResponse = await page.request.post("/api/v1/projects", {
    data: { slug: `visual-a11y-${Date.now()}`, title: "Visual accessibility E2E project" },
  });
  expect(projectResponse.ok()).toBeTruthy();
  const project = await projectResponse.json() as { id: string };
  await page.evaluate(id => window.localStorage.setItem("proseforge.current-project", id), project.id);
  await page.goto(`/projects/${project.id}/studio`);
  await page.emulateMedia({ reducedMotion: "reduce" });
  mkdirSync("/app/artifacts/visual-a11y", { recursive: true });

  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator(".review-pane")).toBeVisible();
    await expect(page.locator(".chat-composer textarea")).toBeVisible();
    const overflow = await page.evaluate(() => ({
      innerWidth: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      elements: Array.from(document.querySelectorAll<HTMLElement>("body *"))
        .filter(element => element.getBoundingClientRect().right > window.innerWidth + 1)
        .slice(0, 8)
        .map(element => ({ tag: element.tagName, className: element.className, right: Math.round(element.getBoundingClientRect().right) })),
    }));
    expect(overflow.scrollWidth, `horizontal overflow at ${width}px: ${JSON.stringify(overflow)}`).toBeLessThanOrEqual(overflow.innerWidth);
    await page.screenshot({ path: `/app/artifacts/visual-a11y/studio-${width}.png`, fullPage: true });
  }

  await page.keyboard.press("Tab");
  await expect.poll(() => page.evaluate(() => document.activeElement?.matches("button, input, textarea, select"))).toBe(true);
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior)).toBe("auto");
});

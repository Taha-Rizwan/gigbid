import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";

test.describe("phone layout", () => {
  test.use({ viewport: { width: 375, height: 812 }, hasTouch: true });

  for (const path of ["/inbox", "/jobs/job_101", "/studio/th_101", "/pipeline", "/messages/conv_1", "/runs/run_101", "/analytics", "/settings"]) {
    test(`no horizontal scroll on ${path}`, async ({ page }) => {
      await mockApi(page);
      await page.goto(path);
      await expect(page.locator("main h1, main h2").first()).toBeVisible();
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }

  test("navigation collapses into a menu button", async ({ page }) => {
    await mockApi(page);
    await page.goto("/inbox");
    const toggle = page.getByTestId("nav-toggle");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByTestId("mobile-nav")).toHaveCount(0);
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await page.getByTestId("mobile-nav").getByRole("link", { name: "Pipeline" }).click();
    await expect(page).toHaveURL(/\/pipeline$/);
    await expect(page.getByTestId("mobile-nav")).toHaveCount(0);
  });
});

test("keyboard: Tab reaches claims in the studio and the focus ring is visible", async ({ page }) => {
  await mockApi(page);
  await page.goto("/studio/th_101");
  await expect(page.getByTestId("approval-panel")).toBeVisible();
  let found = false;
  for (let i = 0; i < 40 && !found; i++) {
    await page.keyboard.press("Tab");
    found = await page.evaluate(() => document.activeElement?.getAttribute("data-testid") === "claim");
  }
  expect(found).toBe(true);
  await expect(page.getByTestId("evidence-card")).toBeVisible();
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement!).outlineStyle);
  expect(outline).toBe("solid");
});

import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";
import * as fx from "./fixtures";

const MESSAGE = "Marketplace unavailable: work is queued and will resume automatically";

test.describe("degraded mode banner", () => {
  test("is hidden while /api/health is ok", async ({ page }) => {
    await mockApi(page);
    await page.goto("/inbox");
    await expect(page.getByTestId("job-row").first()).toBeVisible();
    await expect(page.getByTestId("degraded-banner")).toHaveCount(0);
  });

  test("shows when /api/health reports degraded", async ({ page }) => {
    await mockApi(page, { "GET /api/health": () => ({ json: fx.healthDegraded }) });
    await page.goto("/inbox");
    const banner = page.getByTestId("degraded-banner");
    await expect(banner).toContainText(MESSAGE);
    await expect(banner).toContainText("3 queued");
    await expect(banner).toContainText("marketplace (down)");
  });

  test("shows when any request returns 503 marketplace_unavailable", async ({ page }) => {
    await mockApi(page, {
      "POST /api/jobs/scout": () => ({ status: 503, json: fx.marketplaceUnavailable }),
    });
    await page.goto("/inbox");
    await expect(page.getByTestId("job-row").first()).toBeVisible();
    await expect(page.getByTestId("degraded-banner")).toHaveCount(0);

    await page.getByTestId("scout-now").click();
    await expect(page.getByTestId("degraded-banner")).toContainText(MESSAGE);
  });

  test("clears once health recovers", async ({ page }) => {
    await page.clock.install();
    let health = fx.healthDegraded;
    await mockApi(page, { "GET /api/health": () => ({ json: health }) });
    await page.goto("/inbox");
    await expect(page.getByTestId("degraded-banner")).toBeVisible();
    health = fx.healthOk;
    await page.clock.fastForward(21_000); // the banner polls every 20 s
    await expect(page.getByTestId("degraded-banner")).toHaveCount(0);
  });
});

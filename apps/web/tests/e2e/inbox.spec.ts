import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";

test("inbox ranks jobs, filters, skips with a reason and scouts", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/inbox$/);

  const rows = page.getByTestId("job-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.first().getByTestId("risk-badge")).toHaveAttribute("data-level", "low");
  await expect(rows.nth(2).getByTestId("risk-badge")).toHaveAttribute("data-level", "high");
  await expect(rows.first().getByTestId("review-draft")).toHaveAttribute("href", "/studio/th_101");

  await page.getByTestId("filter-recommendation").selectOption("bid");
  await expect
    .poll(() => api.calls.some((c) => c.path === "/api/jobs" && c.search.includes("recommendation=bid")))
    .toBe(true);

  const scam = page.locator('[data-job-id="job_103"]');
  await scam.getByTestId("skip-job").click();
  await expect(scam.getByTestId("confirm-skip")).toBeDisabled();
  await scam.getByTestId("skip-reason").fill("Off-platform payment request");
  await scam.getByTestId("confirm-skip").click();
  await expect.poll(() => api.find("POST", "/api/jobs/job_103/skip").length).toBe(1);
  expect(api.find("POST", "/api/jobs/job_103/skip")[0].body).toEqual({ reason: "Off-platform payment request" });

  await page.getByTestId("scout-now").click();
  await expect(page.getByTestId("scout-started").getByRole("link")).toHaveAttribute("href", "/runs/run_scout");
});

test("a 401 from the API sends the user to /login", async ({ page }) => {
  await mockApi(page, {
    "GET /api/jobs": () => ({ status: 401, json: { detail: "not signed in" } }),
    "GET /api/auth/me": () => ({ status: 401, json: { detail: "not signed in" } }),
  });
  await page.goto("/inbox");
  await expect(page).toHaveURL(/\/login\?next=%2Finbox/);
});

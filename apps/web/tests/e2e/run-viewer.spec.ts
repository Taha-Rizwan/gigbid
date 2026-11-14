import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";
import * as fx from "./fixtures";

test("streams node-by-node progress over SSE and links to the studio on interrupt", async ({ page }) => {
  let streamed = false;
  await mockApi(page, {
    // After the stream ends with an interrupt, the refetched run is "interrupted".
    "GET /api/runs/:id": ({ req }) => ({ json: req.url().includes("run_101") && streamed ? fx.runInterrupted : fx.run }),
    "GET /api/runs/:id/stream": () => {
      streamed = true;
      return {
        status: 200,
        contentType: "text/event-stream",
        body: fx.runEvents.map((e) => `id: ${e.seq}\ndata: ${JSON.stringify(e)}\n\n`).join(""),
      };
    },
  });

  await page.goto("/runs/run_101");

  const nodes = page.getByTestId("timeline-node");
  await expect(nodes).toHaveCount(5);
  for (const n of ["job_analyst", "risk_assessor", "fit_matcher"]) {
    const lane = page.locator(`[data-testid="timeline-node"][data-node="${n}"]`);
    await expect(lane).toHaveAttribute("data-state", "done");
    await expect(lane).toContainText("parallel");
  }
  await expect(page.locator('[data-node="writer"]')).not.toContainText("parallel");
  await expect(page.locator('[data-node="human_approval"]')).toHaveAttribute("data-state", "interrupted");
  await expect(page.getByTestId("run-event-log").locator("li")).toHaveCount(10);

  await expect(page.getByTestId("run-status")).toHaveText("Interrupted");
  await expect(page.getByTestId("run-tokens")).toContainText("8,270");
  await expect(page.getByTestId("trace-link")).toHaveAttribute("href", fx.run.trace_url!);
  await expect(page.getByTestId("open-studio")).toHaveAttribute("href", "/studio/th_101");
});

test("job detail: Analyze starts a run and opens the live viewer", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/jobs/job_101");
  await expect(page.getByTestId("injection-detected")).toBeVisible();
  await expect(page.getByTestId("matrix-row")).toHaveCount(3);
  await expect(page.locator('[data-testid="matrix-row"][data-covered="false"]')).toContainText("Not covered");
  await expect(page.getByTestId("market-range")).toContainText("$2,200");
  await expect(page.getByTestId("connects-worth-it")).toHaveText("Worth it");

  await page.getByTestId("analyze").click();
  await expect(page).toHaveURL(/\/runs\/run_101/);
  expect(api.find("POST", "/api/jobs/job_101/analyze")).toHaveLength(1);
});

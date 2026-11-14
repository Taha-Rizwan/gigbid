import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";

test("messages: approve a suggested reply through the graph thread", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/messages/conv_1");
  await expect(page.getByTestId("message-list").locator("li")).toHaveCount(2);
  await expect(page.getByTestId("proposed-slots").locator("li")).toHaveCount(2);
  await expect(page.getByTestId("suggested-reply")).toContainText("Tuesday 14:00");
  await expect(page.getByTestId("conversation-item")).toHaveCount(2);
  await expect(page.getByTestId("conversation-item").nth(1)).toContainText("Scam signal");

  await page.getByTestId("approve-button").click();
  await expect(page.getByTestId("approval-outcome")).toBeVisible();
  // Messages reuse the approvals endpoint with the conversation's graph_thread_id.
  expect(api.find("POST", "/api/approvals/th_conv_1")[0].body).toEqual({ action: "approve" });

  await page.getByTestId("draft-reply").click();
  await expect.poll(() => api.find("POST", "/api/messages/conv_1/draft").length).toBe(1);
});

test("pipeline shows all seven stages and polls", async ({ page }) => {
  await page.clock.install();
  const api = await mockApi(page);
  await page.goto("/pipeline");
  for (const s of ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]) {
    await expect(page.getByTestId(`kanban-column-${s}`)).toBeVisible();
  }
  await expect(page.getByTestId("kanban-card")).toHaveCount(2);
  const before = api.find("GET", "/api/pipeline").length;
  await page.clock.fastForward(16_000);
  await expect.poll(() => api.find("GET", "/api/pipeline").length).toBeGreaterThan(before);
});

test("analytics renders KPIs and charts", async ({ page }) => {
  await mockApi(page);
  await page.goto("/analytics");
  const a = page.getByTestId("analytics");
  await expect(a).toContainText("Reply rate");
  await expect(a).toContainText("29%");
  await expect(a).toContainText("21.7 s");
  await expect(a).toContainText("Too generic");
  await expect(a).toContainText("2026-W45");
});

test("settings: autonomy note, save, and forgetting a memory", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/settings");
  await expect(page.getByTestId("no-auto-send")).toContainText("Auto-send is never allowed");
  await page.getByTestId("autonomy-auto_skip_low_fit").check();
  await page.getByTestId("settings-connects-budget").fill("100");
  await page.getByTestId("settings-save").click();
  await expect.poll(() => api.find("PUT", "/api/profile").length).toBe(1);
  expect(api.find("PUT", "/api/profile")[0].body).toMatchObject({ autonomy: "auto_skip_low_fit", weekly_connects_budget: 100 });

  await expect(page.getByTestId("memory-item")).toHaveCount(2);
  await page.getByTestId("memory-delete").first().click();
  await page.getByTestId("memory-confirm-delete").click();
  await expect.poll(() => api.find("DELETE", "/api/memory/style/tone").length).toBe(1);
  await expect(page.getByTestId("connect-upwork")).toHaveAttribute("href", "/api/oauth/upwork/start");
});

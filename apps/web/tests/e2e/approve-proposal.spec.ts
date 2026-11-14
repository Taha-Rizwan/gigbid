import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";
import * as fx from "./fixtures";

test.describe("proposal studio: approve", () => {
  test("shows claims with evidence on hover and keyboard focus", async ({ page }) => {
    await mockApi(page);
    await page.goto("/studio/th_101");

    await expect(page.getByRole("heading", { name: fx.studio.job_title })).toBeVisible();
    await expect(page.getByTestId("unsupported-before")).toHaveText("3");
    await expect(page.getByTestId("unsupported-after")).toHaveText("1");

    const supported = page.locator('[data-testid="claim"][data-label="supported"]');
    await supported.hover();
    const card = page.getByTestId("evidence-card");
    await expect(card).toBeVisible();
    await expect(card).toContainText("Support RAG bot for a SaaS help centre");
    await expect(card).toContainText("Deflected 38% of tickets");

    // Keyboard: the unsupported claim is reachable with Tab and explains itself.
    await page.mouse.move(0, 0);
    const unsupported = page.locator('[data-testid="claim"][data-label="unsupported"]');
    await unsupported.focus();
    await expect(unsupported).toBeFocused();
    await expect(page.getByTestId("evidence-card")).toContainText("No portfolio evidence backs this claim");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("evidence-card")).toHaveCount(0);

    // The critic's paragraph-specific comment is pinned inline under paragraph 3.
    await expect(page.locator('[data-testid="paragraph"][data-index="2"]').getByTestId("comment-critic")).toContainText(
      "Paragraph 3 makes a claim with no evidence",
    );

    // Dry run shows exactly what will be sent and the Connects cost.
    await expect(page.getByTestId("dry-run-connects")).toHaveText("16");
    await expect(page.getByTestId("dry-run-text")).toContainText("deflected 38% of tickets");
  });

  test("approving posts to the approvals endpoint and a refresh reads state from the server", async ({ page }) => {
    let submitted = false;
    const api = await mockApi(page, {
      "GET /api/proposals/:id": () => ({ json: submitted ? fx.studioSubmitted : fx.studio }),
      "POST /api/approvals/:id": () => {
        submitted = true;
        return { json: fx.approvalResult("submitted", "Proposal submitted; 16 Connects spent.") };
      },
    });
    await page.goto("/studio/th_101");

    // A refresh before deciding keeps the pending approval (it comes from the server).
    await expect(page.getByTestId("approval-panel")).toBeVisible();
    await page.reload();
    await expect(page.getByTestId("approval-panel")).toBeVisible();

    await page.getByTestId("approve-button").click();
    await expect(page.getByTestId("approval-outcome")).toContainText("Submitted");

    const calls = api.find("POST", "/api/approvals/th_101");
    expect(calls).toHaveLength(1);
    expect(calls[0].body).toEqual({ action: "approve" });

    // Server now says nothing is pending; the studio reflects that after refresh.
    await page.reload();
    await expect(page.getByTestId("no-pending-approval")).toBeVisible();
    await expect(page.getByTestId("studio-status")).toHaveText("Submitted");
  });

  test("approve is disabled when compliance blocks the draft", async ({ page }) => {
    const blocked = {
      ...fx.studio,
      compliance: { allowed: false, violations: ["Asks the client to email directly"], redactions: [], cleaned_text: null, reason: "off-platform contact" },
      pending_approval: {
        ...fx.studio.pending_approval!,
        compliance: { allowed: false, violations: ["Asks the client to email directly"], redactions: [], cleaned_text: null, reason: "off-platform contact" },
      },
    };
    await mockApi(page, { "GET /api/proposals/:id": () => ({ json: blocked }) });
    await page.goto("/studio/th_101");
    await expect(page.getByTestId("approve-button")).toBeDisabled();
    await expect(page.getByTestId("comment-compliance").first()).toContainText("Asks the client to email directly");
  });
});

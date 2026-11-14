import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";

test("rejecting a proposal requires a reason and sends it", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/studio/th_101");

  await page.getByTestId("reject-button").click();
  await page.getByTestId("submit-reject").click();

  // No reason: blocked client-side, nothing sent.
  await expect(page.getByTestId("reject-form").getByRole("alert")).toContainText("Please give a reason");
  await expect(page.getByTestId("reject-reason")).toHaveAttribute("aria-invalid", "true");
  expect(api.find("POST", "/api/approvals/th_101")).toHaveLength(0);

  await page.getByTestId("reject-reason").fill("Overclaims: I have never built 50 admin panels.");
  await page.getByTestId("submit-reject").click();

  await expect(page.getByTestId("approval-outcome")).toContainText("Rejected");
  const calls = api.find("POST", "/api/approvals/th_101");
  expect(calls).toHaveLength(1);
  expect(calls[0].body).toEqual({
    action: "reject",
    reason: "Overclaims: I have never built 50 admin panels.",
  });
});

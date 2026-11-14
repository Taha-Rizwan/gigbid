import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";
import * as fx from "./fixtures";

test("editing a draft sends edited text and answers", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/studio/th_101");

  await page.getByTestId("edit-button").click();
  const editor = page.getByTestId("edit-textarea");
  await expect(editor).toHaveValue(fx.coverLetter);

  const edited = fx.coverLetter.replace(
    "I have built admin panels for over 50 enterprise clients.",
    "I can build the admin re-index panel in week 3.",
  );
  await editor.fill(edited);
  await page.getByTestId("edit-answer-0").fill("HelpDesk AI: 3,100 articles, inline citations, 38% deflection.");
  await page.getByTestId("submit-edit").click();

  await expect(page.getByTestId("approval-outcome")).toContainText("Rechecking");
  const calls = api.find("POST", "/api/approvals/th_101");
  expect(calls).toHaveLength(1);
  expect(calls[0].body).toEqual({
    action: "edit",
    edited_text: edited,
    edited_answers: ["HelpDesk AI: 3,100 articles, inline citations, 38% deflection."],
  });
});

test("regenerating one paragraph posts its index and instruction", async ({ page }) => {
  const api = await mockApi(page);
  await page.goto("/studio/th_101");
  await page.getByTestId("regenerate-2").click();
  await page.getByTestId("regenerate-instruction-2").fill("Drop the unsupported claim");
  await page.getByTestId("regenerate-submit-2").click();
  await expect(page.getByRole("link", { name: "watch run" })).toHaveAttribute("href", "/runs/run_regen");
  expect(api.find("POST", "/api/proposals/th_101/regenerate")[0].body).toEqual({
    paragraph_index: 2,
    instruction: "Drop the unsupported claim",
  });
});

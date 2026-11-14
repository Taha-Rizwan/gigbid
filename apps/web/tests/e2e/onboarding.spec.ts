import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";
import * as fx from "./fixtures";

test.describe("sign-in and onboarding", () => {
  test("registering a new account leads to onboarding", async ({ page }) => {
    const api = await mockApi(page);
    await page.goto("/login");
    await page.getByTestId("tab-register").click();
    await page.getByTestId("auth-name").fill("New User");
    await page.getByTestId("auth-email").fill("new@example.com");
    await page.getByTestId("auth-password").fill("correct-horse-1");
    await page.getByTestId("auth-submit").click();

    await expect(page).toHaveURL(/\/onboarding$/);
    expect(api.find("POST", "/api/auth/register")[0].body).toEqual({
      name: "New User",
      email: "new@example.com",
      password: "correct-horse-1",
    });
  });

  test("a wrong password shows an inline error, not a redirect", async ({ page }) => {
    await mockApi(page, {
      "POST /api/auth/login": () => ({ status: 401, json: { detail: "Invalid email or password" } }),
    });
    await page.goto("/login");
    await page.getByTestId("auth-email").fill("amira@example.com");
    await page.getByTestId("auth-password").fill("nope-nope");
    await page.getByTestId("auth-submit").click();
    await expect(page.getByTestId("auth-form").getByRole("alert")).toContainText("Invalid email or password");
    await expect(page).toHaveURL(/\/login/);
  });

  test("walks persona, marketplace, portfolio upload and preferences", async ({ page }) => {
    const api = await mockApi(page, {
      "GET /api/profile": () => ({ status: 404, json: { detail: "no profile yet" } }),
      "GET /api/auth/me": () => ({ json: fx.newUser }),
      "GET /api/searches": () => ({ json: [] }),
      "GET /api/portfolio/items": () => ({ json: [] }),
    });
    await page.goto("/onboarding");

    // 1. Persona
    await page.getByTestId("persona-fullstack").check();
    await page.getByTestId("display-title").fill("Full-stack dev, Next.js + FastAPI");
    await page.getByTestId("onboarding-next").click();

    // 2. Marketplace: Upwork shows the OAuth link, then switch back to GigSim
    await page.getByTestId("marketplace-upwork_live").check();
    await expect(page.getByTestId("connect-upwork")).toHaveAttribute("href", "/api/oauth/upwork/start");
    await page.getByTestId("marketplace-gigsim").check();
    await page.getByTestId("onboarding-next").click();

    // 3. Portfolio upload (multipart)
    await page.getByTestId("portfolio-input").setInputFiles({
      name: "case-study.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# HelpDesk AI\nRAG bot that deflected 38% of tickets."),
    });
    await page.getByTestId("portfolio-upload").click();
    await expect(page.getByTestId("upload-result")).toContainText("Added 1 item");
    const upload = api.find("POST", "/api/portfolio/upload")[0];
    expect(upload.contentType).toContain("multipart/form-data");
    expect(String(upload.body)).toContain('name="files"; filename="case-study.md"');
    await page.getByTestId("onboarding-next").click();

    // 4. Preferences + saved search
    await page.getByTestId("hourly-floor").fill("50");
    await page.getByTestId("fixed-floor").fill("400");
    await page.getByTestId("connects-budget").fill("60");
    await page.getByTestId("excluded-keywords").fill("crypto, unpaid test");
    await page.getByTestId("search-query").fill("Next.js dashboard");
    await page.getByTestId("add-search").click();
    await expect.poll(() => api.find("POST", "/api/searches").length).toBe(1);
    expect(api.find("POST", "/api/searches")[0].body).toMatchObject({
      query: "Next.js dashboard",
      interval_minutes: 30,
      enabled: true,
    });

    await page.getByTestId("onboarding-finish").click();
    await expect(page).toHaveURL(/\/inbox$/);

    const put = api.find("PUT", "/api/profile")[0];
    expect(put.body).toEqual({
      persona: "fullstack",
      display_title: "Full-stack dev, Next.js + FastAPI",
      hourly_floor: 50,
      fixed_floor: 400,
      weekly_connects_budget: 60,
      excluded_keywords: ["crypto", "unpaid test"],
      autonomy: "manual",
      marketplace_mode: "gigsim",
      model_profile: "open",
    });
  });
});

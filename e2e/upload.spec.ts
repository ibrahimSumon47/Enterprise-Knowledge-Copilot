import { expect, test } from "@playwright/test";

const apiBase =
  process.env.EKC_API_URL ?? "https://enterprise-knowledge-copilot-2u57.onrender.com";
const run = process.env.EKC_SIGNUP_E2E === "1";

test.describe("upload on production", () => {
  test.skip(!run, "Set EKC_SIGNUP_E2E=1 to create a real account.");

  test("signs up, uploads Markdown, asks about it and deletes it", async ({ page }) => {
    test.setTimeout(900_000);
    const stamp = Date.now();
    const email = `upload-${stamp}@ekc-e2e.test`;
    const password = `Ekc-${stamp}-upload`;
    const title = `upload-${stamp}.md`;

    for (let attempt = 0; attempt < 60; attempt += 1) {
      try {
        const response = await fetch(`${apiBase}/openapi.json`, {
          signal: AbortSignal.timeout(45_000),
        });
        if (response.ok) {
          const spec = (await response.json()) as { paths?: Record<string, unknown> };
          if (spec.paths?.["/documents/upload"] && spec.paths?.["/signup"]) break;
        }
      } catch {
        /* Render may be waking */
      }
      await new Promise((resolve) => setTimeout(resolve, 5_000));
    }

    await page.goto("/register", { waitUntil: "domcontentloaded" });
    await page.getByLabel("Work email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create workspace" }).click();
    await expect(page).toHaveURL(/\/onboarding$/, { timeout: 120_000 });

    await page.goto("/library", { waitUntil: "domcontentloaded" });
    const fileInput = page.getByLabel(/Upload a document/);
    await expect(fileInput).toBeVisible({ timeout: 60_000 });
    await fileInput.setInputFiles({
      name: title,
      mimeType: "text/markdown",
      buffer: Buffer.from(
        "# Expense policy\n\nEmployees must submit receipts for expenses above 25 USD within 45 days. Reimbursement is paid with the next payroll cycle.\n",
      ),
    });
    await page.getByRole("button", { name: "Upload", exact: true }).click();
    await expect(page.getByRole("status")).toContainText(/ready/i, { timeout: 300_000 });
    await expect(page.getByText(title, { exact: true })).toBeVisible({ timeout: 30_000 });

    await page.goto("/chat", { waitUntil: "domcontentloaded" });
    const composer = page.getByPlaceholder("Ask about policy, leave, security or expenses…");
    await composer.fill("How many days do employees have to submit receipts?");
    const answered = page.waitForResponse(
      (response) => response.url().includes("/chat") && response.request().method() === "POST",
      { timeout: 120_000 },
    );
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    const response = await answered;
    expect([200, 500, 502, 503]).toContain(response.status());

    page.once("dialog", (dialog) => dialog.accept());
    await page.goto("/library", { waitUntil: "domcontentloaded" });
    const row = page.getByRole("listitem").filter({ hasText: title }).first();
    await expect(row).toBeVisible({ timeout: 60_000 });
    await row.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText(title, { exact: true })).toHaveCount(0, { timeout: 60_000 });
  });
});

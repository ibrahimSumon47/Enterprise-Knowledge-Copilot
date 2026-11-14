import { expect, test } from "@playwright/test";

const apiBase =
  process.env.EKC_API_URL ?? "https://enterprise-knowledge-copilot-2u57.onrender.com";

const run = process.env.EKC_SIGNUP_E2E === "1";

test.describe("workspace sign-up on production", () => {
  test.skip(!run, "Set EKC_SIGNUP_E2E=1 to create a real account.");

  test("signs up, names the workspace, adds a document and reaches chat", async ({
    page,
  }) => {
    test.setTimeout(600_000);
    const stamp = Date.now();
    const email = `signup-${stamp}@ekc-e2e.test`;
    const password = `Ekc-${stamp}-passphrase`;

    // Render rebuilds independently of Vercel; wait for the route to exist rather
    // than testing the previous deployment.
    let deployed = false;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      try {
        const response = await fetch(`${apiBase}/openapi.json`, {
          signal: AbortSignal.timeout(60_000),
        });
        if (response.ok) {
          const spec = (await response.json()) as { paths?: Record<string, unknown> };
          if (spec.paths?.["/signup"]) {
            deployed = true;
            break;
          }
        }
      } catch {
        /* the free instance may be waking up */
      }
      await new Promise((resolve) => setTimeout(resolve, 5_000));
    }
    expect(deployed, "the deployed API exposes POST /signup").toBe(true);

    await page.goto("/register", { waitUntil: "domcontentloaded" });
    await page.getByLabel("Work email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create workspace" }).click();
    await expect(page).toHaveURL(/\/onboarding$/, { timeout: 120_000 });

    const workspace = `E2E workspace ${stamp}`;
    await page.getByLabel("Workspace name").fill(workspace);
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByRole("heading", { name: workspace })).toBeVisible({
      timeout: 60_000,
    });

    await page
      .getByLabel("Document title")
      .fill("Expense policy");
    await page
      .getByLabel("Document text")
      .fill(
        "Expense policy for the E2E workspace. Employees must submit receipts for expenses above 25 USD within 45 days. Reimbursement is paid with the next payroll cycle.",
      );
    await page.getByRole("button", { name: "Add document" }).click();
    const ask = page.getByRole("button", { name: "Ask a question" });
    await expect(ask).toBeEnabled({ timeout: 120_000 });
    await ask.click();
    await expect(page).toHaveURL(/\/chat$/, { timeout: 60_000 });
  });
});

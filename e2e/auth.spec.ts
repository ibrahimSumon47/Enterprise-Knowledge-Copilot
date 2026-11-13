import { expect, test, type Page } from "@playwright/test";

const password = process.env.EKC_DEMO_PASSWORD ?? "";
const apiBase =
  process.env.EKC_API_URL ?? "https://enterprise-knowledge-copilot-2u57.onrender.com";

const roles = [
  { email: "guest@ekc.local", label: "guest", admin: false },
  { email: "employee@ekc.local", label: "employee", admin: false },
  { email: "engineering@ekc.local", label: "engineering", admin: false },
  { email: "security@ekc.local", label: "security", admin: false },
  { email: "hr@ekc.local", label: "people", admin: false },
  { email: "finance@ekc.local", label: "finance", admin: false },
  { email: "admin@ekc.local", label: "administrator", admin: true },
];

test.beforeAll(async () => {
  if (!password) {
    throw new Error(
      "EKC_DEMO_PASSWORD is required: these tests sign in as the real role accounts.",
    );
  }
  // The API sleeps on the free tier. Wake it once so role lookups do not time out.
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      const response = await fetch(`${apiBase}/health`, {
        signal: AbortSignal.timeout(60_000),
      });
      if (response.ok) return;
    } catch {
      /* retry while the instance boots */
    }
    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
});

async function signIn(page: Page, email: string) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await expect(page.locator("form[data-auth-version='2']")).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/, { timeout: 45_000 });
}

test("the sign-in form cannot fall back to a native GET submit", async ({ page }) => {
  const leaked: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("password=")) leaked.push(request.url());
  });
  await page.goto("/login");
  const form = page.locator("form[data-auth-version='2']");
  await expect(form).toHaveAttribute("method", "post");
  await page.getByLabel("Email").fill("admin@ekc.local");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  expect(leaked).toEqual([]);
});

for (const role of roles) {
  test(`${role.label} signs in through the form and keeps the session`, async ({ page }) => {
    await signIn(page, role.email);
    await expect(page.getByRole("heading", { name: "Ask the handbook" })).toBeVisible();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/chat$/);
    await expect(page.getByText(`Signed in as ${role.email}`)).toBeVisible();

    await page.goto("/admin", { waitUntil: "domcontentloaded" });
    if (role.admin) {
      await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();
    } else {
      await expect(page.getByRole("heading", { name: "Administrators only" })).toBeVisible();
    }
  });
}

test("signing out returns to the form and the session is gone", async ({ page }) => {
  await signIn(page, "employee@ekc.local");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/, { timeout: 45_000 });
  await page.goto("/chat", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/login\?next=%2Fchat/, { timeout: 45_000 });
});

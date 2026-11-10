import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const samples = path.resolve(__dirname, "../../samples");
const password = "e2e-password-123";

async function signUp(page: Page, email: string) {
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL("**/home");
}

test("protected pages redirect to login", async ({ page }) => {
  await page.goto("/history");
  await expect(page).toHaveURL(/\/login/);
});

test("anonymous API access is rejected", async ({ request }) => {
  expect((await request.get("/api/backend/jobs")).status()).toBe(401);
  expect((await request.get("/api/upload?fileName=a.pdf&fileType=application/pdf")).status()).toBe(401);
});

test("wrong password shows an error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("nobody@example.com");
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid email or password")).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("upload, review, download, admin approval", async ({ browser }) => {
  const stamp = Date.now();
  const applicantContext = await browser.newContext();
  const page = await applicantContext.newPage();
  const consoleErrors: string[] = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  await signUp(page, `applicant-${stamp}@example.com`);

  await page.goto("/upload");
  await expect(page.getByRole("heading", { name: /E2E Tester/ })).toBeVisible();
  await page.getByLabel("1. Provider Document").setInputFiles(path.join(samples, "cvs/generated_cv_1.pdf"));
  await page.getByLabel("2. Fillable PDF Form").setInputFiles(path.join(samples, "forms/weehope_tx_application.pdf"));
  await page.getByRole("button", { name: "Start AI Extraction" }).click();

  await expect(page.getByRole("heading", { name: "Filled Form" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Page 1 of 17/)).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".react-pdf__Page canvas")).toBeVisible();

  await page.getByRole("button", { name: /Show \d+ blank fields/ }).click();
  await page.getByLabel("Specialty", { exact: true }).fill("Neurology");
  await page.getByRole("button", { name: "Save & Submit" }).click();
  await expect(page.getByText("The PDF now includes your confirmed values")).toBeVisible({ timeout: 30_000 });

  const download = page.waitForEvent("download");
  await page.getByLabel("Download PDF").click();
  expect((await download).suggestedFilename()).toBe("filled_form.pdf");

  await page.goto("/history");
  await expect(page.getByText("Awaiting admin")).toBeVisible();
  expect(consoleErrors.filter((e) => /hydrat|<html>/i.test(e))).toEqual([]);

  const adminContext = await browser.newContext();
  const admin = await adminContext.newPage();
  await signUp(admin, "e2e-admin@example.com").catch(async () => {
    await admin.goto("/login");
    await admin.getByLabel("Email").fill("e2e-admin@example.com");
    await admin.getByLabel("Password").fill(password);
    await admin.getByRole("button", { name: "Sign in" }).click();
    await admin.waitForURL("**/home");
  });
  await admin.goto("/admin");
  const row = admin.getByRole("row", { name: new RegExp(`applicant-${stamp}`) });
  await row.getByRole("button", { name: "Send Forward" }).click();
  await expect(row).toHaveCount(0);

  await page.reload();
  await expect(page.getByText("Approved")).toBeVisible();

  const logout = page.getByRole("button", { name: "Logout" });
  await logout.click();
  await page.waitForURL("http://localhost:3000/");
  await page.goto("/upload");
  await expect(page).toHaveURL(/\/login/);
});

test("non-admin cannot use the admin dashboard", async ({ page }) => {
  await signUp(page, `plain-${Date.now()}@example.com`);
  await page.goto("/admin");
  await expect(page.getByText("You do not have admin access.")).toBeVisible();
});

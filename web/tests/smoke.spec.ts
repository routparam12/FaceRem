import { test, expect, Page } from "@playwright/test";
import { generateTotp } from "./totp-helper";
import { execSync } from "node:child_process";

async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.fill('input[autocomplete="organization"]', "northwind");
  await page.fill('input[type="email"]', "admin@northwind.demo");
  await page.fill('input[type="password"]', "demo12345");
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL(/\/dashboard/);
}

test.describe.serial("Smoke Tests (One per page)", () => {
  test.beforeAll(() => {
    try {
      execSync(
        `python -c "import sqlite3; con = sqlite3.connect('d:/ML/FaceRem/test_faceattend.db'); con.execute(\\"UPDATE users SET is_totp_enabled = 0, totp_secret = NULL WHERE email = 'hr@northwind.demo'\\"); con.commit(); con.close()"`
      );
    } catch (e) {
      console.error("Failed to reset TOTP for hr@northwind.demo:", e);
    }
  });

  test("01: Sign in with valid admin credentials", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[autocomplete="organization"]', "northwind");
    await page.fill('input[type="email"]', "admin@northwind.demo");
    await page.fill('input[type="password"]', "demo12345");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.locator("h1")).toContainText(/Northwind Industries|Your workspace/);
  });

  test("02: Employee-only account cannot sign in to web console", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[autocomplete="organization"]', "northwind");
    await page.fill('input[type="email"]', "employee@northwind.demo");
    await page.fill('input[type="password"]', "demo12345");
    await page.click('button[type="submit"]');

    // Should stay on login and show error banner
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText("Email or password is incorrect.")).toBeVisible();
  });

  test("03: TOTP setup and TOTP sign-in flow", async ({ page }) => {
    // 1. Sign in as HR admin who has no TOTP yet
    await page.goto("/login");
    await page.fill('input[autocomplete="organization"]', "northwind");
    await page.fill('input[type="email"]', "hr@northwind.demo");
    await page.fill('input[type="password"]', "demo12345");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);

    // 2. Navigate to security settings
    await page.goto("/dashboard/settings/security");
    await expect(page.locator("h1")).toContainText("Security Settings");

    // 3. Click Configure Two-Factor Auth
    const configureBtn = page.getByRole("button", { name: "Configure Two-Factor Auth" });
    if (await configureBtn.isVisible()) {
      await configureBtn.click();

      // 4. Extract secret key from displayed code element
      const secretCodeElem = page.locator("code");
      await expect(secretCodeElem).toBeVisible();
      const secret = (await secretCodeElem.textContent())?.trim();
      expect(secret).toBeTruthy();

      // 5. Generate TOTP code and submit
      const totpCode = generateTotp(secret!);
      await page.getByLabel("Verification code").fill(totpCode);
      await page.getByRole("button", { name: "Activate 2FA" }).click();

      // 6. Verify recovery codes are displayed
      await expect(page.getByText("Two-Factor Authentication is Active!")).toBeVisible({
        timeout: 15000,
      });
      await expect(page.getByText("Save your Emergency Recovery Codes")).toBeVisible();
      const recoveryCodeElems = page.locator(".grid.grid-cols-2 > div");
      await expect(recoveryCodeElems).toHaveCount(8);

      // Click Done
      await page.getByRole("button", { name: "Done" }).click();

      // 7. Sign out
      await page.getByRole("button", { name: "Sign out" }).click();
      await expect(page).toHaveURL(/\/login/);

      // 8. Sign in again -> requires 2FA
      await page.fill('input[autocomplete="organization"]', "northwind");
      await page.fill('input[type="email"]', "hr@northwind.demo");
      await page.fill('input[type="password"]', "demo12345");
      await page.click('button[type="submit"]');

      // Verify 2FA challenge screen appears
      await expect(page.getByText("Two-Factor Authentication Required")).toBeVisible();
      const newTotp = generateTotp(secret!);
      await page.getByLabel("Verification or recovery code").fill(newTotp);
      await page.getByRole("button", { name: "Confirm Sign In" }).click();

      // Successfully entered dashboard
      await expect(page).toHaveURL(/\/dashboard/);
    }
  });

  test("04: Employees (create, set PIN, deactivate)", async ({ page }) => {
    // Sign in as admin
    await page.goto("/login");
    await page.fill('input[autocomplete="organization"]', "northwind");
    await page.fill('input[type="email"]', "admin@northwind.demo");
    await page.fill('input[type="password"]', "demo12345");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);

    // Go to employees list
    await page.goto("/dashboard/employees");
    await expect(page.locator("h1")).toContainText("People");

    // Click Add employee
    await page.getByRole("link", { name: "Add employee" }).click();
    await expect(page).toHaveURL(/\/dashboard\/employees\/new/);

    // Fill form using exact labels
    const code = `NW-TEST-${Date.now().toString().slice(-4)}`;
    await page.getByLabel("Full name").fill("Automation Employee");
    await page.getByLabel("Work email").fill(`auto.${Date.now()}@northwind.demo`);
    await page.getByLabel("Employee code").fill(code);
    await page.getByRole("button", { name: "Save employee" }).click();

    // Should redirect to employee detail page
    await expect(page).toHaveURL(/\/dashboard\/employees\/[\w-]+/);
    await expect(page.locator("h1")).toContainText("Automation Employee");

    // Set PIN
    await page.getByLabel("Set / Reset 4-6 Digit PIN").fill("4321");
    await page.getByRole("button", { name: "Save Fallback PIN" }).click();
    await expect(page.getByText("Fallback PIN configured successfully.")).toBeVisible();

    // Deactivate employee
    await page.getByRole("button", { name: "Deactivate Employee" }).click();
    await expect(page.getByText("Deactivated")).toBeVisible();
  });

  test("05: Devices (create enrollment code, revoke)", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/dashboard/devices");
    await expect(page.locator("h1")).toContainText("Kiosk Devices");

    // Click Register New Kiosk
    await page.getByRole("button", { name: "+ Register New Kiosk" }).click();

    // Modal opens showing 6-character code
    await expect(page.getByText("Device Enrollment Code")).toBeVisible();
    const codeElem = page.locator("span.font-mono.tracking-widest");
    await expect(codeElem).toBeVisible();
    const code = (await codeElem.textContent())?.trim();
    expect(code).toHaveLength(6);

    // Close modal
    await page.getByRole("button", { name: "Done" }).click();

    // Revoke an active device if present
    const revokeBtn = page.getByRole("button", { name: "Revoke" }).first();
    if (await revokeBtn.isVisible()) {
      await revokeBtn.click();
      await expect(page.getByText("Revoke Kiosk Device?")).toBeVisible();
      await page.getByRole("button", { name: "Revoke Device" }).click();
      await expect(page.getByText("REVOKED").first()).toBeVisible();
    }
  });

  test("06: Cameras (add, edit)", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/dashboard/cameras");
    await expect(page.locator("h1")).toContainText("Cameras");

    // Add camera
    await page.getByRole("button", { name: "+ Add Camera" }).click();
    await expect(page.getByText("Add Camera Source")).toBeVisible();

    const cameraName = `Gate-${Date.now().toString().slice(-4)}`;
    await page.getByLabel("Camera Name").fill(cameraName);
    await page.getByRole("button", { name: "Add Camera", exact: true }).click();

    // Verify camera in table
    await expect(page.getByText(cameraName)).toBeVisible();

    // Edit camera
    const editBtn = page.locator("tr").filter({ hasText: cameraName }).getByRole("button", { name: "Configure" });
    await editBtn.click();
    await expect(page.getByText("Configure Camera")).toBeVisible();

    const updatedName = `${cameraName}-Updated`;
    await page.getByLabel("Camera Name").fill(updatedName);
    await page.getByRole("button", { name: "Save Changes" }).click();

    await expect(page.getByText(updatedName)).toBeVisible();
  });

  test("07: Attendance (filter, void with reason)", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/dashboard/attendance");
    await expect(page.locator("h1")).toContainText("Attendance Center");

    // Check filter interaction
    const searchInput = page.getByPlaceholder(/Search employee name/i);
    await searchInput.fill("Aarav");
    await page.waitForTimeout(300);

    // Clear filter
    await searchInput.fill("");

    // Test void button if an active event exists
    const voidBtn = page.getByRole("button", { name: "Void" }).first();
    if (await voidBtn.isVisible()) {
      await voidBtn.click();
      await expect(page.getByText("Void Attendance Event")).toBeVisible();

      await page.getByLabel(/Reason for Voiding/i).fill("Smoke test manual voiding");
      await page.getByRole("button", { name: "Confirm Void" }).click();

      // Verify event shows VOIDED
      await expect(page.getByText("VOIDED").first()).toBeVisible();
    }
  });

  test("08: Reports (CSV download, UTF-8 BOM, cell with = neutralized)", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/dashboard/reports");
    await expect(page.locator("h1")).toContainText("Reports & Data Export");

    // Verify CSV download via API proxy with active session
    const response = await page.request.get("/api/proxy/api/v1/reports/attendance-events.csv");
    expect(response.status()).toBe(200);

    const contentType = response.headers()["content-type"];
    expect(contentType).toContain("text/csv");

    const bodyBuffer = await response.body();
    // Check UTF-8 BOM (0xEF, 0xBB, 0xBF)
    expect(bodyBuffer[0]).toBe(0xef);
    expect(bodyBuffer[1]).toBe(0xbb);
    expect(bodyBuffer[2]).toBe(0xbf);

    // Check CSV content: any cell starting with = must be neutralized to '=
    const csvText = bodyBuffer.toString("utf-8");
    const lines = csvText.split("\r\n").filter((l) => l.trim().length > 0);
    expect(lines.length).toBeGreaterThan(1); // Header + at least one row

    for (const line of lines) {
      const cells = line.split(",");
      for (const cell of cells) {
        expect(cell.startsWith("=")).toBeFalsy();
      }
    }
  });

  test("09: Organization timezone settings", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/dashboard/settings");
    await expect(page.locator("h1")).toContainText("Organization Settings");

    // Select timezone
    const tzSelect = page.locator("select");
    await tzSelect.selectOption("Asia/Kolkata");

    // Click Save Settings
    await page.getByRole("button", { name: "Save Settings" }).click();
    await expect(page.getByText("Organization configuration saved successfully.")).toBeVisible();

    // Reload and assert persisted
    await page.reload();
    await expect(tzSelect).toHaveValue("Asia/Kolkata");
  });

  test("10: Sign out and session termination", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Sign out" }).click();

    await expect(page).toHaveURL(/\/login/);

    // Attempt direct navigation to /dashboard should redirect
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login\?expired=1/);
  });

  test("11: Manager sees no mutation controls and API refuses mutation", async ({ page }) => {
    // 1. Sign in as manager
    await page.goto("/login");
    await page.fill('input[autocomplete="organization"]', "northwind");
    await page.fill('input[type="email"]', "manager@northwind.demo");
    await page.fill('input[type="password"]', "demo12345");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);

    // 2. On /dashboard/employees: "Add employee" button MUST NOT be present
    await page.goto("/dashboard/employees");
    await expect(page.locator("h1")).toContainText("People");
    await expect(page.getByRole("link", { name: "Add employee" })).toHaveCount(0);

    // 3. API proxy MUST refuse mutation from manager (HTTP 403)
    const mutateRes = await page.evaluate(async () => {
      const res = await fetch("/api/proxy/api/v1/employees", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: "Illegal Employee",
          employee_code: "MGR-ILLEGAL",
          email: "illegal@northwind.demo",
        }),
      });
      return { status: res.status, body: await res.json() };
    });

    expect(mutateRes.status).toBe(403);
    expect(mutateRes.body.error?.code).toBe("FORBIDDEN");
  });
});

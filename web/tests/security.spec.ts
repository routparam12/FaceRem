import { test, expect } from "@playwright/test";

test.describe.serial("Security Checks in Browser", () => {
  test.beforeEach(async ({ page }) => {
    // Sign in as admin to establish session cookies
    await page.goto("/login");
    await page.fill('input[autocomplete="organization"]', "northwind");
    await page.fill('input[type="email"]', "admin@northwind.demo");
    await page.fill('input[type="password"]', "demo12345");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("01: CSRF - POST to proxy with no Origin and no Sec-Fetch-Site is rejected with 403", async ({ page }) => {
    // Send request via APIRequestContext directly with stripped headers
    const res = await page.request.post("/api/proxy/api/v1/employees", {
      headers: {
        // Explicitly omit Origin and Sec-Fetch-Site
        "Content-Type": "application/json",
      },
      data: {
        full_name: "Attacker Employee",
        employee_code: "ATTACK-01",
        email: "attacker@evil.com",
      },
    });

    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body.error?.code).toBe("CSRF_ERROR");
  });

  test("02: CSRF - Cross-origin POST is rejected with 403", async ({ page }) => {
    // Send request with an untrusted Origin
    const res = await page.request.post("/api/proxy/api/v1/employees", {
      headers: {
        "Origin": "http://evil-attacker.example.com",
        "Content-Type": "application/json",
      },
      data: {
        full_name: "Attacker Employee",
        employee_code: "ATTACK-02",
        email: "attacker2@evil.com",
      },
    });

    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body.error?.code).toBe("CSRF_ERROR");
  });

  test("03: Cookies in session are httpOnly and SameSite=Lax", async ({ page, context }) => {
    const cookies = await context.cookies();
    const accessCookie = cookies.find((c) => c.name === "fa_access");
    const refreshCookie = cookies.find((c) => c.name === "fa_refresh");

    expect(accessCookie).toBeDefined();
    expect(refreshCookie).toBeDefined();

    // Verify httpOnly
    expect(accessCookie?.httpOnly).toBe(true);
    expect(refreshCookie?.httpOnly).toBe(true);

    // Verify SameSite
    expect(accessCookie?.sameSite.toLowerCase()).toBe("lax");
    expect(refreshCookie?.sameSite.toLowerCase()).toBe("lax");
  });

  test("04: No tokens or secrets stored in localStorage or sessionStorage", async ({ page }) => {
    await page.goto("/dashboard");

    const storage = await page.evaluate(() => {
      return {
        local: { ...window.localStorage },
        session: { ...window.sessionStorage },
      };
    });

    // Check localStorage
    for (const [key, value] of Object.entries(storage.local)) {
      expect(key.toLowerCase()).not.toContain("token");
      expect(key.toLowerCase()).not.toContain("secret");
      expect(String(value)).not.toContain("eyJ"); // No raw JWTs
    }

    // Check sessionStorage
    for (const [key, value] of Object.entries(storage.session)) {
      expect(key.toLowerCase()).not.toContain("token");
      expect(key.toLowerCase()).not.toContain("secret");
      expect(String(value)).not.toContain("eyJ");
    }
  });

  test("05: No sensitive secrets exposed in API responses", async ({ page }) => {
    // 1. Employees endpoint: no PIN or pin_hash
    const empRes = await page.request.get("/api/proxy/api/v1/employees");
    expect(empRes.status()).toBe(200);
    const emps = (await empRes.json()).data;
    for (const emp of emps) {
      expect(emp).not.toHaveProperty("pin");
      expect(emp).not.toHaveProperty("pin_hash");
    }

    // 2. Devices endpoint: no enrollment code
    const devRes = await page.request.get("/api/proxy/api/v1/devices");
    expect(devRes.status()).toBe(200);
    const devs = (await devRes.json()).data;
    for (const dev of devs) {
      expect(dev).not.toHaveProperty("enrollment_code");
      expect(dev).not.toHaveProperty("code");
    }

    // 3. Organization endpoint: no secrets or credentials
    const orgRes = await page.request.get("/api/proxy/api/v1/organization");
    expect(orgRes.status()).toBe(200);
    const org = (await orgRes.json()).data;
    expect(org).not.toHaveProperty("secret");
    expect(org).not.toHaveProperty("jwt_secret");
  });
});


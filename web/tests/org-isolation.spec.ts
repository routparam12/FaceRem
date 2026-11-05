import { test, expect } from "@playwright/test";

test.describe.serial("Multi-Tenant Organization Isolation via Web Layer", () => {
  let acmeEmployeeId: string;
  let acmeDeviceId: string;
  let acmeCameraId: string;

  test("01: Gather Org B (Acme) resource IDs as Acme Admin", async ({ browser }) => {
    // Create an isolated context for Acme
    const context = await browser.newContext();
    const page = await context.newPage();

    // Sign in as Acme admin
    await page.goto("/login");
    await page.fill('input[autocomplete="organization"]', "acme");
    await page.fill('input[type="email"]', "admin@acme.demo");
    await page.fill('input[type="password"]', "demo12345");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);

    // Get Acme employees
    const empRes = await page.request.get("/api/proxy/api/v1/employees");
    expect(empRes.status()).toBe(200);
    const emps = (await empRes.json()).data;
    expect(emps.length).toBeGreaterThan(0);
    acmeEmployeeId = emps[0].id;

    // Get Acme devices
    const devRes = await page.request.get("/api/proxy/api/v1/devices");
    expect(devRes.status()).toBe(200);
    const devs = (await devRes.json()).data;
    expect(devs.length).toBeGreaterThan(0);
    acmeDeviceId = devs[0].id;

    // Get Acme cameras
    const camRes = await page.request.get("/api/proxy/api/v1/cameras");
    expect(camRes.status()).toBe(200);
    const cams = (await camRes.json()).data;
    if (cams.length > 0) {
      acmeCameraId = cams[0].id;
    }

    await context.close();
  });

  test("02: Admin of Org A (Northwind) cannot access Org B (Acme) resources", async ({ page }) => {
    // Sign in as Northwind admin
    await page.goto("/login");
    await page.fill('input[autocomplete="organization"]', "northwind");
    await page.fill('input[type="email"]', "admin@northwind.demo");
    await page.fill('input[type="password"]', "demo12345");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);

    // 1. Employees list: MUST NOT contain any Acme employees (prefix AC-)
    const empRes = await page.request.get("/api/proxy/api/v1/employees");
    expect(empRes.status()).toBe(200);
    const emps = (await empRes.json()).data;
    for (const emp of emps) {
      expect(emp.employee_code.startsWith("AC-")).toBeFalsy();
      expect(emp.id).not.toBe(acmeEmployeeId);
    }

    // 2. Direct read of Acme employee: MUST fail with 404
    const getAcmeEmp = await page.request.get(`/api/proxy/api/v1/employees/${acmeEmployeeId}`);
    expect(getAcmeEmp.status()).toBe(404);

    // 3. Direct modification of Acme employee: MUST fail with 404 / 403
    const patchAcmeEmp = await page.request.patch(`/api/proxy/api/v1/employees/${acmeEmployeeId}`, {
      data: { full_name: "Hacked Acme Name" },
    });
    expect([403, 404]).toContain(patchAcmeEmp.status());

    // 4. Devices list: MUST NOT contain Acme's device
    const devRes = await page.request.get("/api/proxy/api/v1/devices");
    expect(devRes.status()).toBe(200);
    const devs = (await devRes.json()).data;
    for (const dev of devs) {
      expect(dev.id).not.toBe(acmeDeviceId);
    }

    // 5. Direct modification of Acme device: MUST fail with 404
    const patchAcmeDev = await page.request.patch(`/api/proxy/api/v1/devices/${acmeDeviceId}`, {
      data: { name: "Hacked Kiosk" },
    });
    expect([403, 404]).toContain(patchAcmeDev.status());

    // 6. Cameras list: MUST NOT contain Acme cameras
    if (acmeCameraId) {
      const camRes = await page.request.get("/api/proxy/api/v1/cameras");
      expect(camRes.status()).toBe(200);
      const cams = (await camRes.json()).data;
      for (const cam of cams) {
        expect(cam.id).not.toBe(acmeCameraId);
      }

      // Direct modification of Acme camera: MUST fail with 404
      const patchAcmeCam = await page.request.patch(`/api/proxy/api/v1/cameras/${acmeCameraId}`, {
        data: { name: "Hacked Camera" },
      });
      expect([403, 404]).toContain(patchAcmeCam.status());
    }

    // 7. Attendance events: MUST NOT contain Acme events
    const evRes = await page.request.get("/api/proxy/api/v1/attendance/events");
    expect(evRes.status()).toBe(200);
    const events = (await evRes.json()).data;
    for (const ev of events) {
      expect(ev.employee_id).not.toBe(acmeEmployeeId);
      expect(ev.device_id).not.toBe(acmeDeviceId);
    }

    // 8. Audit logs: MUST NOT contain Acme audit records
    // Directly query backend /api/v1/audit-logs or proxy
    const auditRes = await page.request.get("/api/proxy/api/v1/audit-logs");
    // If proxied or forbidden
    if (auditRes.status() === 200) {
      const logs = (await auditRes.json()).data;
      for (const log of logs) {
        expect(log.target_id).not.toBe(acmeEmployeeId);
        expect(log.target_id).not.toBe(acmeDeviceId);
      }
    }
  });
});


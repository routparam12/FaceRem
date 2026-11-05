import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir ..\\backend --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
      env: {
        DATABASE_URL: "sqlite:///d:/ML/FaceRem/test_faceattend.db",
        JWT_SECRET: "test-secret-that-is-long-enough-for-hs256-abcdef",
        FACE_ENGINE: "stub",
        LIVENESS_MODE: "disabled",
        SEED_DEMO_DATA: "true",
      },
    },
    {
      command: "npx next start -p 3000",
      url: "http://127.0.0.1:3000/login",
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
      env: {
        API_BASE_URL: "http://127.0.0.1:8000",
      },
    },
  ],
});


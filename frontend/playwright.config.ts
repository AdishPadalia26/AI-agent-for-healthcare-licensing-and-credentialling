import { defineConfig } from "@playwright/test";

// Test-only values. The stack runs offline with LLM_PROVIDER=local and OCR_PROVIDER=local.
const SECRET = "playwright-only-secret-playwright-only-secret";
const PYTHON = process.env.BACKEND_PYTHON ?? "python";
const DATA_DIR = process.env.E2E_DATA_DIR ?? "../backend/data/e2e";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  workers: 1,
  use: { baseURL: "http://localhost:3000" },
  webServer: [
    {
      command: `"${PYTHON}" -c "from app import app; app.run(port=5000)"`,
      cwd: "../backend",
      url: "http://127.0.0.1:5000/api/health",
      reuseExistingServer: false,
      env: {
        LLM_PROVIDER: "local",
        OCR_PROVIDER: "local",
        STORAGE_BACKEND: "local",
        BACKEND_JWT_SECRET: SECRET,
        DATA_DIR,
        ADMIN_EMAILS: "e2e-admin@example.com",
        PYTHONDONTWRITEBYTECODE: "1",
      },
    },
    {
      command: "npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: false,
      timeout: 120_000,
      env: { NEXTAUTH_SECRET: SECRET, NEXTAUTH_URL: "http://localhost:3000", BACKEND_URL: "http://127.0.0.1:5000" },
    },
  ],
});

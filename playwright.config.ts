import { defineConfig } from "@playwright/test";
import { validateTarget } from "./tests/browser_config";

const target = process.env.TEST_BASE_URL;
validateTarget(target);
export default defineConfig({
  testDir: "tests/browser",
  testMatch: process.env.TEST_READ_FAILURE
    ? "**/errors.spec.ts"
    : "**/settings.spec.ts",
  workers: 1,
  retries: 0,
  timeout: 45000,
  outputDir: "artifacts/browser/results",
  reporter: [["list"]],
  use: { baseURL: target, trace: "off", screenshot: "off", video: "off" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1920, height: 1080 } } },
    {
      name: "desktop-de",
      use: { viewport: { width: 1920, height: 1080 }, locale: "de-DE" },
    },
    { name: "compact", use: { viewport: { width: 768, height: 900 } } },
  ],
});

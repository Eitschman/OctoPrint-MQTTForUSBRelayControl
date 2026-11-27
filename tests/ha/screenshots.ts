import { chromium, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const target = process.env.TEST_HA_URL;
const token = process.env.TEST_HA_TOKEN;
const device = process.env.TEST_HA_DEVICE_ID;
if (!target || !token || !device)
  throw new Error("Disposable HA parameters are required");
const parsed = new URL(target);
if (
  parsed.protocol !== "http:" ||
  parsed.hostname !== "127.0.0.1" ||
  !parsed.port ||
  parsed.pathname !== "/" ||
  parsed.username ||
  parsed.password ||
  parsed.search ||
  parsed.hash
) {
  throw new Error("HA screenshots require an owned loopback test instance");
}
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    locale: "en-US",
  });
  await context.addInitScript(
    ({ accessToken, url }) => {
      localStorage.setItem(
        "hassTokens",
        JSON.stringify({
          access_token: accessToken,
          token_type: "Bearer",
          expires_in: 1800,
          expires: Date.now() + 1800000,
          clientId: url + "/",
          hassUrl: url,
        }),
      );
    },
    { accessToken: token, url: target },
  );
  const page = await context.newPage();
  await page.goto(target + "/config/entities");
  const confirm = page.getByRole("button", { name: "Confirm", exact: true });
  await confirm.click({ timeout: 30000 });
  await expect(confirm).toBeHidden();
  await expect(page.locator("#ha-launch-screen")).toBeHidden({
    timeout: 30000,
  });
  await page
    .getByText("Synthetic enclosure light", { exact: true })
    .first()
    .waitFor({ timeout: 30000 });
  await mkdir("artifacts/browser/screenshots", { recursive: true });
  await page.screenshot({
    path: "artifacts/browser/screenshots/ha-entities.png",
  });
  await page.goto(target + "/config/devices/device/" + device);
  await page
    .getByText("Synthetic printer", { exact: true })
    .first()
    .waitFor({ timeout: 20000 });
  await page.getByText("Controls", { exact: true }).waitFor();
  await expect(page.locator("#ha-launch-screen")).toBeHidden({
    timeout: 30000,
  });
  await page.screenshot({
    path: "artifacts/browser/screenshots/ha-device.png",
  });
  await context.close();
} finally {
  await browser.close();
}

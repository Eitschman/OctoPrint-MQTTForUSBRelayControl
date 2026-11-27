import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { requireCredentials } from "../browser_config";

test("UI04 actual read failure is Unknown with an explicit diagnostic", async ({
  page,
  context,
}) => {
  requireCredentials(process.env.TEST_USERNAME, process.env.TEST_PASSWORD);
  await page.goto("/");
  const csrf = (await context.cookies()).find((cookie) =>
    cookie.name.startsWith("csrf_token"),
  );
  if (!csrf) throw new Error("The disposable CSRF cookie is missing");
  const response = await context.request.post("/api/login", {
    headers: { "X-CSRF-Token": decodeURIComponent(csrf.value) },
    data: { user: process.env.TEST_USERNAME, pass: process.env.TEST_PASSWORD },
  });
  expect(response.status()).toBe(200);
  await page.reload();
  await page.locator("#navbar_settings a").click();
  await page
    .locator('a[href="#settings_plugin_mqttforusbrelaycontrol"]')
    .click();
  const panel = page.locator("#settings_plugin_mqttforusbrelaycontrol");
  await expect(panel.getByText("Unknown", { exact: true })).toBeVisible();
  await expect(
    panel.getByText("Read failed: OSError", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByText("Off", { exact: true })).toHaveCount(0);
  await expect(page.locator("#settings_dialog")).toHaveCSS("opacity", "1");
  await mkdir("artifacts/browser/screenshots", { recursive: true });
  await panel.screenshot({
    path: "artifacts/browser/screenshots/read-failure.png",
  });
});

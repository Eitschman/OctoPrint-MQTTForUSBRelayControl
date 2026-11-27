import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { requireCredentials } from "../browser_config";
import { checkAppearance } from "./appearance";

test("UI01 UI02 UI06 UI07 UI08 settings and original relay bridge", async ({
  page,
  context,
}, testInfo) => {
  const target = process.env.TEST_BASE_URL;
  const username = process.env.TEST_USERNAME;
  const password = process.env.TEST_PASSWORD;
  test.skip(!target, "Run through the disposable OctoPrint fixture");
  requireCredentials(username, password);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const german = testInfo.project.name.endsWith("-de");
  const text = {
    enable: german ? "MQTT-Integration aktivieren" : "Enable MQTT integration",
    unknown: german ? "Unbekannt" : "Unknown",
    on: german ? "Ein" : "On",
    name: german ? "Home-Assistant-Name" : "Home Assistant name",
    read: german ? "Aktuelle Zustände lesen" : "Read current states",
    connected: german ? "Verbunden" : "Connected",
    save: german ? "Speichern" : "Save",
    grouping: german
      ? "Vorhandenes OctoPrint-Gerät verwenden, wenn verfügbar"
      : "Use existing OctoPrint device when available",
    identifier: german
      ? "Gerätekennung überschreiben (optional)"
      : "Device identifier override (optional)",
    maxAge: german
      ? "Maximales Befehlsalter (Sekunden)"
      : "Maximum command age (seconds)",
    interval: german
      ? "Mindestabstand pro Kanal (Sekunden)"
      : "Minimum channel interval (seconds)",
  };
  await page.goto(german ? "/?l10n=de" : "/");
  const cookies = await context.cookies();
  const csrf = cookies.find((cookie) => cookie.name.startsWith("csrf_token"));
  if (!csrf) throw new Error("The isolated OctoPrint CSRF cookie is missing");
  const login = await context.request.post("/api/login", {
    headers: { "X-CSRF-Token": decodeURIComponent(csrf.value) },
    data: { user: username, pass: password, remember: false },
  });
  expect(login.status()).toBe(200);
  await page.reload();
  await page.locator("#navbar_settings a").click();
  await page
    .locator('a[href="#settings_plugin_mqttforusbrelaycontrol"]')
    .click();
  const panel = page.locator("#settings_plugin_mqttforusbrelaycontrol");
  await expect(
    panel.getByText("Synthetic work light with a long accessible name", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(panel.getByLabel(text.enable, { exact: true })).toBeChecked();
  await expect(panel.getByText(text.unknown, { exact: true })).toHaveCount(0);
  if (!process.env.TEST_PYTHON)
    throw new Error("The disposable fixture interpreter is required");
  execFileSync(process.env.TEST_PYTHON, ["tests/browser_publish.py"], {
    stdio: "pipe",
  });
  await expect(panel.getByText(text.on, { exact: true })).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const scope = window as unknown as {
          ko: {
            dataFor: (element: Element) => {
              usbrelayButtons: () => { current_state: string }[];
            };
          };
        };
        const sidebar = document.querySelector(
          "#sidebar_plugin_usbrelaycontrol",
        );
        return (
          sidebar &&
          scope.ko.dataFor(sidebar).usbrelayButtons()[0].current_state
        );
      }),
    )
    .toBe("on");
  const name = panel.getByLabel(text.name, { exact: true });
  await name.fill("Unsaved test name");
  await expect(name).toHaveValue("Unsaved test name");
  await panel.locator("summary").click();
  const grouping = panel.getByLabel(text.grouping, { exact: true });
  const identifier = panel.getByLabel(text.identifier, { exact: true });
  const maxAge = panel.getByLabel(text.maxAge, { exact: true });
  const interval = panel.getByLabel(text.interval, { exact: true });
  await test.step("Device grouping controls allow unsaved overrides", async () => {
    await expect(grouping).toBeChecked();
    await expect(identifier).toHaveValue("");
    await grouping.uncheck();
    await identifier.fill("Synthetic-device-ID");
    await expect(grouping).not.toBeChecked();
    await expect(identifier).toHaveValue("Synthetic-device-ID");
  });
  await test.step("Command protection permits unsaved timing changes", async () => {
    await expect(maxAge).toHaveValue("5");
    await expect(interval).toHaveValue("0.25");
    await maxAge.fill("7");
    await interval.fill("0.5");
  });
  await expect(
    panel.getByRole("button", { name: text.read, exact: true }),
  ).toBeEnabled();
  await panel.getByRole("button", { name: text.read, exact: true }).click();
  await expect(panel.getByText(text.connected, { exact: true })).toBeVisible();
  await test.step("Readable settings in light and dark host themes", async () => {
    await mkdir("artifacts/browser/screenshots", { recursive: true });
    await checkAppearance(page, panel, testInfo.project.name);
  });
  const box = await panel.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x + box!.width).toBeLessThanOrEqual(
    testInfo.project.use.viewport!.width,
  );
  await panel.locator("summary").click();
  await panel.scrollIntoViewIfNeeded();
  await mkdir("artifacts/browser/screenshots", { recursive: true });
  await panel.screenshot({
    path: `artifacts/browser/screenshots/settings-${testInfo.project.name}.png`,
  });
  await page
    .locator("#settings_dialog")
    .locator('[data-test-id="settings-close-button"]')
    .click();
  const originalOff = page
    .locator("#sidebar_plugin_usbrelaycontrol")
    .getByRole("button", { name: "OFF", exact: true });
  await expect(originalOff).toBeEnabled();
  await originalOff.click();
  execFileSync(
    process.env.TEST_PYTHON!,
    ["tests/browser_publish.py", "--expect-off"],
    { stdio: "pipe" },
  );
  await page.locator("#navbar_settings a").click();
  await page
    .locator('a[href="#settings_plugin_mqttforusbrelaycontrol"]')
    .click();
  await expect(name).not.toHaveValue("Unsaved test name");
  await panel.locator("summary").click();
  await expect(grouping).toBeChecked();
  await expect(identifier).toHaveValue("");
  await expect(maxAge).toHaveValue("5");
  await expect(interval).toHaveValue("0.25");
  await maxAge.fill("7");
  await interval.fill("0.5");
  await panel.locator("summary").click();
  await name.fill("Saved disposable light");
  await page
    .locator("#settings_dialog")
    .getByRole("button", { name: text.save, exact: true })
    .click();
  await expect(page.locator("#settings_dialog")).toBeHidden();
  await page.locator("#navbar_settings a").click();
  await page
    .locator('a[href="#settings_plugin_mqttforusbrelaycontrol"]')
    .click();
  await expect(name).toHaveValue("Saved disposable light");
  await panel.locator("summary").click();
  await expect(maxAge).toHaveValue("7");
  await expect(interval).toHaveValue("0.5");
  expect(errors).toEqual([]);
});

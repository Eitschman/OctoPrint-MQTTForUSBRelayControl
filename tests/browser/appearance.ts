import { expect, type Locator, type Page } from "@playwright/test";

/** Capture the rendered viewport without resizing a fixed OctoPrint modal. */
export async function capturePanel(page: Page, panel: Locator, path: string) {
  const box = await panel.boundingBox();
  const viewport = page.viewportSize();
  if (!box || !viewport)
    throw new Error("The visible settings viewport is unavailable");
  const x = Math.max(0, box.x);
  const y = Math.max(0, box.y);
  const width = Math.min(viewport.width, box.x + box.width) - x;
  const height = Math.min(viewport.height, box.y + box.height) - y;
  expect(width).toBeGreaterThan(300);
  expect(height).toBeGreaterThan(300);
  await page.screenshot({
    path,
    clip: { x, y, width, height },
    animations: "disabled",
  });
}

/** Exercise host theme inheritance independently of the operating system theme. */
export async function checkAppearance(
  page: Page,
  panel: Locator,
  name: string,
) {
  try {
    for (const dark of [false, true]) {
      const theme = dark ? "dark" : "light";
      const foreground = dark ? "rgb(226, 226, 226)" : "rgb(51, 51, 51)";
      await page.emulateMedia({ colorScheme: dark ? "light" : "dark" });
      const style = await page.addStyleTag({
        content: `
          body, #settings_dialog, #settings_dialog .modal-body {
            color: ${foreground};
            background: ${dark ? "#36393e" : "#ffffff"};
          }
          #settings_dialog input, #settings_dialog select {
            color: ${foreground};
            background: ${dark ? "#626773" : "#ffffff"};
          }
        `,
      });
      try {
        const text = panel.locator(
          "label, dt, dd, summary, h3, h4, h5, " +
            ".mqtt-relay-note, .mqtt-relay-save-note, " +
            ".mqtt-relay-health strong, .mqtt-relay-identity code, " +
            "input[type=text], input[type=number], select",
        );
        expect(await text.count()).toBeGreaterThan(25);
        for (const element of await text.all())
          await expect(element, `${theme}: inherited text color`).toHaveCSS(
            "color",
            foreground,
          );
        for (const field of await panel
          .locator("input[type=text], input[type=number], select")
          .all())
          await expect(field, `${theme}: host control background`).toHaveCSS(
            "background-color",
            dark ? "rgb(98, 103, 115)" : "rgb(255, 255, 255)",
          );
        await capturePanel(
          page,
          panel,
          `artifacts/browser/screenshots/settings-${name}-${theme}-advanced.png`,
        );
      } finally {
        await style.evaluate((element) =>
          element.parentNode?.removeChild(element),
        );
      }
    }
  } finally {
    await page.emulateMedia({ colorScheme: null });
  }
}

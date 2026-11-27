import { expect, type Locator, type Page } from "@playwright/test";

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
        await panel.screenshot({
          path: `artifacts/browser/screenshots/settings-${name}-${theme}-advanced.png`,
        });
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

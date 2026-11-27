import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { expect, test } from "vitest";
import ko from "knockout";

test("UI03 UI05 message ordering, metadata refresh and server restart", () => {
  type Model = {
    onBeforeBinding: () => void;
    onServerReconnect: () => void;
    onSettingsBeforeSave: () => void;
    deviceSourceText: () => string;
    deviceWarningText: () => string;
    durationText: (seconds: unknown) => string;
    operationText: (kind: string | null) => string;
    onDataUpdaterPluginMessage: (id: string, data: unknown) => void;
    rows: () => {
      original_name: string;
      display_name: (value?: string) => string;
    }[];
    status: () => { epoch: number; revision: number };
  };
  const callbacks: ((data: unknown) => void)[] = [];
  const registrations: { construct: new (parameters: unknown[]) => Model }[] =
    [];
  const scope = {
    ko,
    gettext: (value: string) => value,
    $: (callback: () => void) => callback(),
    OCTOPRINT_VIEWMODELS: registrations,
    OctoPrint: {
      simpleApiGet: () => ({
        done: (callback: (data: unknown) => void) => callbacks.push(callback),
      }),
    },
  };
  runInNewContext(
    readFileSync(
      "octoprint_mqttforusbrelaycontrol/static/js/mqttforusbrelaycontrol.js",
      "utf8",
    ),
    scope,
  );
  const id = "mqttforusbrelaycontrol";
  const ownSettings = {
    relays: {},
    command_max_age: ko.observable<string | number>("5"),
    command_min_interval: ko.observable<string | number>("0.25"),
  };
  const model = new registrations[0].construct([
    { settings: { plugins: { [id]: ownSettings } } },
    { isAdmin: () => true },
    undefined,
  ]);
  model.onBeforeBinding();
  const row = {
    id: "synthetic",
    original_name: "Original name",
    snapshot: { actual: true },
  };
  const message = { schema: 1, epoch: 4, revision: 8, relays: [row] };
  model.onDataUpdaterPluginMessage(id, message);
  model.rows()[0].display_name("Unsaved edit");
  model.onDataUpdaterPluginMessage(id, { ...message, revision: 7 });
  expect(model.status().revision).toBe(8);
  model.onDataUpdaterPluginMessage(id, {
    ...message,
    revision: 9,
    relays: [{ ...row, original_name: "Renamed" }],
  });
  expect(model.rows()[0].original_name).toBe("Renamed");
  expect(model.rows()[0].display_name()).toBe("Unsaved edit");
  model.onDataUpdaterPluginMessage(id, { ...message, epoch: undefined });
  expect(model.status().revision).toBe(9);
  model.onServerReconnect();
  callbacks[1]({ ...message, epoch: 0, revision: 1 });
  callbacks[0](message);
  expect(model.status().epoch).toBe(0);
  model.onSettingsBeforeSave();
  expect(ownSettings.command_max_age()).toBe(5);
  expect(ownSettings.command_min_interval()).toBe(0.25);
  expect(model.durationText(null)).toBe("—");
  expect(model.durationText(2.005)).toBe("2.00 s");
  expect(model.operationText("write")).toBe("Writing");
  expect(model.operationText(null)).toBe("Idle");
  model.onDataUpdaterPluginMessage(id, {
    ...message,
    epoch: 0,
    revision: 2,
    device_source: "octoprint",
    device_warning: "cached",
  });
  expect(model.deviceSourceText()).toBe("HomeAssistant Discovery");
  expect(model.deviceWarningText()).toContain("last confirmed assignment");
  model.onDataUpdaterPluginMessage(id, {
    ...message,
    epoch: 0,
    revision: 3,
    device_source: "custom",
    device_warning: null,
  });
  expect(model.deviceSourceText()).toBe("Custom identifier");
  expect(model.deviceWarningText()).toBe("");
});

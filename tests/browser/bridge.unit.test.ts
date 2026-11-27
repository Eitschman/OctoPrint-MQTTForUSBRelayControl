import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it } from "vitest";
import ko from "knockout";

type Row = {
  vendor: string;
  product: string;
  channel: number;
  active_mode: string;
  index: number;
  snapshot: { actual: boolean | null };
};
type Bridge = {
  compatible: boolean;
  update: (rows: Row[]) => void;
  dispose: () => void;
};
const scope = {
  ko,
  MQTTUSBRelayUI: undefined as
    undefined | { createBridge: (original: unknown, ko: unknown) => Bridge },
};
runInNewContext(
  readFileSync(
    "octoprint_mqttforusbrelaycontrol/static/js/mqttforusbrelaycontrol.js",
    "utf8",
  ),
  scope,
);
const row: Row = {
  vendor: "16c0",
  product: "05df",
  channel: 1,
  index: 0,
  active_mode: "active_high",
  snapshot: { actual: true },
};
function original() {
  return {
    usbrelayButtons: ko.observableArray([
      { name: "Light", current_state: "off" },
    ]),
    usbrelayConfigurations: ko.observableArray([
      {
        vendor: "16C0",
        product: "05df",
        relaynumber: "1",
        active_mode: "active_high",
      },
    ]),
  };
}
describe("companion bridge", () => {
  it("UI03 updates plain original items and resists a delayed REST overwrite", () => {
    const model = original();
    const bridge = scope.MQTTUSBRelayUI!.createBridge(model, ko);
    expect(bridge.compatible).toBe(true);
    bridge.update([row]);
    expect(model.usbrelayButtons()[0].current_state).toBe("on");
    model.usbrelayButtons.replace(model.usbrelayButtons()[0], {
      name: "Light",
      current_state: "off",
    });
    expect(model.usbrelayButtons()[0].current_state).toBe("on");
    bridge.dispose();
  });
  it("UI04 rejects mismatched configuration and represents unknown explicitly", () => {
    const model = original();
    const bridge = scope.MQTTUSBRelayUI!.createBridge(model, ko);
    bridge.update([{ ...row, channel: 2 }]);
    expect(model.usbrelayButtons()[0].current_state).toBe("off");
    bridge.update([{ ...row, snapshot: { actual: null } }]);
    expect(model.usbrelayButtons()[0].current_state).toBe("unknown");
  });
  it("UI05 missing original model stays inert", () => {
    const bridge = scope.MQTTUSBRelayUI!.createBridge(undefined, ko);
    expect(bridge.compatible).toBe(false);
    expect(() => bridge.update([row])).not.toThrow();
  });
});

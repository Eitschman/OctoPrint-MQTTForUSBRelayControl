import { expect, test } from "vitest";
import { requireCredentials, validateTarget } from "./browser_config";

test("V15 validates the target before credentials can be used", () => {
  expect(() => validateTarget(undefined)).not.toThrow();
  expect(() => validateTarget("http://127.0.0.1:43210")).not.toThrow();
  for (const target of [
    "https://127.0.0.1:43210",
    "http://example.com:43210",
    "http://localhost:43210",
    "http://127.0.0.1",
    "http://user:password@127.0.0.1:43210",
    "http://127.0.0.1:43210/private",
    "http://127.0.0.1:43210/?token=test",
    "invalid",
  ]) {
    expect(() => validateTarget(target)).toThrow();
  }
  expect(() => requireCredentials("disposable", "synthetic")).not.toThrow();
  expect(() => requireCredentials(undefined, "synthetic")).toThrow();
  expect(() => requireCredentials("disposable", "")).toThrow();
});

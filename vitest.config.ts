import { defineConfig } from "vitest/config";
export default defineConfig({
  test: {
    include: [
      "tests/browser/**/*.unit.test.ts",
      "tests/browser_config.test.ts",
    ],
    environment: "node",
  },
});

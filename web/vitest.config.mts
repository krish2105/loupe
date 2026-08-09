import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // The player store is framework-free by design, so it needs no DOM. Keeping
    // the default environment means no jsdom dependency and a faster CI run.
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});

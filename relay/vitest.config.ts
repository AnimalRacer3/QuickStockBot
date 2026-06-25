import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["src/**/*.test.ts"],
    testTimeout: 10000,
    hookTimeout: 15000,
    // Sequential execution — tests share real network ports
    sequence: { concurrent: false },
    pool: "threads",
    poolOptions: { threads: { singleThread: true } },
  },
});

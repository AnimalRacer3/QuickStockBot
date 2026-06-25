import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    environmentMatchGlobs: [
      // library / server-side tests use Node (no DOM needed, native modules)
      ["src/lib/**/*.test.ts", "node"],
    ],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});

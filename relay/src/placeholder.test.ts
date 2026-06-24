import { describe, expect, it } from "vitest";
import { greet } from "./placeholder.js";

describe("placeholder", () => {
  it("returns a greeting", () => {
    expect(greet("world")).toBe("hello world");
  });

  it("uses the provided name", () => {
    expect(greet("QuickStockBot")).toBe("hello QuickStockBot");
  });
});

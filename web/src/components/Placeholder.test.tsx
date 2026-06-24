import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Placeholder } from "./Placeholder";

describe("Placeholder", () => {
  it("renders the app heading", () => {
    render(<Placeholder />);
    expect(screen.getByRole("heading", { name: "QuickStockBot" })).toBeDefined();
  });

  it("renders the coming-soon message", () => {
    render(<Placeholder />);
    expect(screen.getByText(/coming soon/i)).toBeDefined();
  });
});

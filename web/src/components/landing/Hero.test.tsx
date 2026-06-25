import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Hero } from "./Hero";

describe("Hero", () => {
  it("renders the primary headline", () => {
    render(<Hero />);
    expect(screen.getByRole("heading", { level: 1 })).toBeDefined();
  });

  it("renders the sign-up CTA", () => {
    render(<Hero />);
    const cta = screen.getByRole("link", { name: /start 1 month free/i });
    expect(cta).toBeDefined();
    expect((cta as HTMLAnchorElement).href).toContain("/signup");
  });

  it("renders the 'no credit card' notice", () => {
    render(<Hero />);
    expect(screen.getByText(/no credit card required/i)).toBeDefined();
  });

  it("renders terminal preview with ticker symbols", () => {
    render(<Hero />);
    expect(screen.getByText("AAPL")).toBeDefined();
    expect(screen.getByText("MSFT")).toBeDefined();
  });
});

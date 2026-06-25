import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Pricing } from "./Pricing";

describe("Pricing", () => {
  it("renders the section heading", () => {
    render(<Pricing />);
    expect(screen.getByRole("heading", { name: /simple, honest pricing/i })).toBeDefined();
  });

  it("renders the monthly price", () => {
    render(<Pricing />);
    expect(screen.getByText("$6.99")).toBeDefined();
  });

  it("renders the free trial badge", () => {
    render(<Pricing />);
    expect(screen.getByText(/1 month free/i)).toBeDefined();
  });

  it("renders the sign-up CTA link", () => {
    render(<Pricing />);
    const cta = screen.getByRole("link", { name: /start free trial/i });
    expect(cta).toBeDefined();
    expect((cta as HTMLAnchorElement).href).toContain("/signup");
  });

  it("renders the no-credit-card notice", () => {
    render(<Pricing />);
    expect(screen.getAllByText(/no credit card required/i).length).toBeGreaterThan(0);
  });

  it("renders the feature list", () => {
    render(<Pricing />);
    expect(screen.getByRole("list", { name: /plan features/i })).toBeDefined();
  });
});

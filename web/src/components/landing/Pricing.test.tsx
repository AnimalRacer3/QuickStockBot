import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Pricing } from "./Pricing";

describe("Pricing", () => {
  it("renders the section heading", () => {
    render(<Pricing />);
    expect(screen.getByRole("heading", { name: /simple, transparent pricing/i })).toBeDefined();
  });

  it("renders both plan names", () => {
    render(<Pricing />);
    expect(screen.getByRole("heading", { name: /^basic$/i })).toBeDefined();
    expect(screen.getByRole("heading", { name: /^premium$/i })).toBeDefined();
  });

  it("renders the basic plan price", () => {
    render(<Pricing />);
    expect(screen.getByText("$4.99")).toBeDefined();
  });

  it("renders the premium plan price", () => {
    render(<Pricing />);
    expect(screen.getByText("$6.99")).toBeDefined();
  });

  it("renders the free trial badge on premium card", () => {
    render(<Pricing />);
    expect(screen.getByText(/1 month free trial/i)).toBeDefined();
  });

  it("renders the premium sign-up CTA link", () => {
    render(<Pricing />);
    const cta = screen.getByTestId("pricing-cta-premium");
    expect(cta).toBeDefined();
    expect((cta as HTMLAnchorElement).href).toContain("/signup");
  });

  it("renders the basic sign-up CTA link", () => {
    render(<Pricing />);
    const cta = screen.getByTestId("pricing-cta-basic");
    expect(cta).toBeDefined();
    expect((cta as HTMLAnchorElement).href).toContain("/signup");
  });

  it("renders the no-credit-card notice", () => {
    render(<Pricing />);
    expect(screen.getAllByText(/no credit card required/i).length).toBeGreaterThan(0);
  });

  it("renders both feature lists", () => {
    render(<Pricing />);
    expect(screen.getByRole("list", { name: /basic plan features/i })).toBeDefined();
    expect(screen.getByRole("list", { name: /premium plan features/i })).toBeDefined();
  });

  it("shows mobile access as excluded on basic and included on premium", () => {
    render(<Pricing />);
    expect(screen.getByText(/full mobile access/i)).toBeDefined();
  });
});

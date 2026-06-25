import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RiskSizingControl } from "./RiskSizingControl";

function setup(
  overrides: {
    dailyPct?: number;
    riskPct?: number;
    overrideEnabled?: boolean;
    onOverrideChange?: (v: boolean) => void;
    onRiskChange?: (v: number) => void;
    riskError?: string;
  } = {}
) {
  const props = {
    dailyPct: overrides.dailyPct ?? 5.0,
    riskPct: overrides.riskPct ?? 1.0,
    overrideEnabled: overrides.overrideEnabled ?? false,
    onOverrideChange: overrides.onOverrideChange ?? vi.fn(),
    onRiskChange: overrides.onRiskChange ?? vi.fn(),
    riskError: overrides.riskError,
  };
  return render(<RiskSizingControl {...props} />);
}

describe("RiskSizingControl", () => {
  it("renders the risk input", () => {
    setup();
    const input = screen.getByLabelText<HTMLInputElement>("Risk per trade percent");
    expect(input).toBeDefined();
  });

  it("input is disabled (greyed) by default", () => {
    setup();
    const input = screen.getByLabelText<HTMLInputElement>("Risk per trade percent");
    expect(input.disabled).toBe(true);
  });

  it("renders override checkbox unchecked by default", () => {
    setup();
    const checkbox = screen.getByLabelText<HTMLInputElement>("Override risk per trade");
    expect(checkbox.checked).toBe(false);
  });

  it("calls onOverrideChange when checkbox toggled", () => {
    const spy = vi.fn();
    setup({ onOverrideChange: spy });
    const checkbox = screen.getByLabelText("Override risk per trade");
    fireEvent.click(checkbox);
    expect(spy).toHaveBeenCalledWith(true);
  });

  it("input is enabled when overrideEnabled=true", () => {
    setup({ overrideEnabled: true });
    const input = screen.getByLabelText<HTMLInputElement>("Risk per trade percent");
    expect(input.disabled).toBe(false);
  });

  it("calls onRiskChange when input value changes (override enabled)", () => {
    const spy = vi.fn();
    setup({ overrideEnabled: true, onRiskChange: spy });
    const input = screen.getByLabelText("Risk per trade percent");
    fireEvent.change(input, { target: { value: "0.8" } });
    expect(spy).toHaveBeenCalledWith(0.8);
  });

  it("shows goal-post N = ceil(daily / risk)", () => {
    setup({ dailyPct: 5.0, riskPct: 1.0 });
    // ceil(5 / 1) = 5 trades
    const liveRegion = screen.getByText(/Goal: reach daily target/);
    expect(liveRegion.textContent).toContain("5");
  });

  it("goal-post updates when risk changes", () => {
    const { rerender } = setup({ dailyPct: 5.0, riskPct: 1.0 });
    // ceil(5/2) = 3
    rerender(
      <RiskSizingControl
        dailyPct={5.0}
        riskPct={2.0}
        overrideEnabled={true}
        onOverrideChange={vi.fn()}
        onRiskChange={vi.fn()}
      />
    );
    const liveRegion = screen.getByText(/Goal: reach daily target/);
    expect(liveRegion.textContent).toContain("3");
  });

  it("shows riskError when provided", () => {
    setup({ riskError: "Must be less than daily target (5%)" });
    const err = screen.getByRole("alert");
    expect(err.textContent).toContain("Must be less than daily target");
  });

  it("shows no error when riskError is undefined", () => {
    setup();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("goal-post uses aria-live polite", () => {
    setup();
    const liveRegion = screen.getByText(/Goal: reach daily target/).closest("[aria-live]");
    expect(liveRegion?.getAttribute("aria-live")).toBe("polite");
  });
});

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CalendarGrid } from "./CalendarGrid";
import type { DailyPL } from "@/lib/types";

const DAYS: DailyPL[] = [
  { date: "2024-03-05", total_pl: 150.0, trade_count: 3 },
  { date: "2024-03-12", total_pl: -80.5, trade_count: 2 },
  { date: "2024-03-19", total_pl: 0, trade_count: 1 },
];

function renderCalendar(overrides: Partial<DailyPL>[] = [], onDayClick = vi.fn()) {
  const days = overrides.length > 0 ? (overrides as DailyPL[]) : DAYS;
  return render(
    <CalendarGrid
      year={2024}
      month={3}
      days={days}
      onDayClick={onDayClick}
      onPrevMonth={vi.fn()}
      onNextMonth={vi.fn()}
    />,
  );
}

describe("CalendarGrid", () => {
  it("renders the month title", () => {
    renderCalendar();
    expect(screen.getByText("March 2024")).toBeDefined();
  });

  it("renders profit day in green", () => {
    renderCalendar();
    const cell = screen.getByTestId("calendar-day-2024-03-05");
    expect(cell.dataset.color).toBe("green");
  });

  it("renders loss day in red", () => {
    renderCalendar();
    const cell = screen.getByTestId("calendar-day-2024-03-12");
    expect(cell.dataset.color).toBe("red");
  });

  it("renders flat/ran day in blue", () => {
    renderCalendar();
    const cell = screen.getByTestId("calendar-day-2024-03-19");
    expect(cell.dataset.color).toBe("blue");
  });

  it("non-run days have no color", () => {
    renderCalendar();
    const cell = screen.getByTestId("calendar-day-2024-03-01");
    expect(cell.dataset.color).toBe("");
  });

  it("shows P&L amounts on run days", () => {
    renderCalendar();
    expect(screen.getByTestId("calendar-pl-2024-03-05").textContent).toBe("+150");
    expect(screen.getByTestId("calendar-pl-2024-03-12").textContent).toBe("-81");
  });

  it("shows flat label on zero P&L day", () => {
    renderCalendar();
    expect(screen.getByTestId("calendar-pl-2024-03-19").textContent).toBe("Flat");
  });

  it("calls onDayClick when clicking a run day", () => {
    const spy = vi.fn();
    renderCalendar(undefined, spy);
    fireEvent.click(screen.getByTestId("calendar-day-2024-03-05"));
    expect(spy).toHaveBeenCalledWith(DAYS[0]);
  });

  it("does not call onDayClick for non-run days", () => {
    const spy = vi.fn();
    renderCalendar(undefined, spy);
    fireEvent.click(screen.getByTestId("calendar-day-2024-03-01"));
    expect(spy).not.toHaveBeenCalled();
  });

  it("calls onPrevMonth and onNextMonth", () => {
    const prevSpy = vi.fn();
    const nextSpy = vi.fn();
    render(
      <CalendarGrid
        year={2024}
        month={3}
        days={[]}
        onPrevMonth={prevSpy}
        onNextMonth={nextSpy}
      />,
    );
    fireEvent.click(screen.getByLabelText("Previous month"));
    expect(prevSpy).toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("Next month"));
    expect(nextSpy).toHaveBeenCalled();
  });

  it("renders legend", () => {
    renderCalendar();
    expect(screen.getByText("Profit")).toBeDefined();
    expect(screen.getByText("Loss")).toBeDefined();
    expect(screen.getByText("Ran / Flat")).toBeDefined();
  });
});

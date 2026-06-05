// frontend/src/__tests__/signals/SignalThemeBlock.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalThemeBlock from "sections/activities/signals/SignalThemeBlock";

afterEach(() => {
  cleanup();
});

const MOCK_SIGNALS = [
  { id: "p1", status: "PENDING", summary: "Pain A", _signalType: "pain" },
  { id: "o1", status: "VALIDATED", summary: "Obj B", _signalType: "objective" },
  { id: "i1", status: "PENDING", summary: "Impact C", _signalType: "impact" },
];

describe("SignalThemeBlock", () => {
  it("renders theme label and count", () => {
    render(
      <SignalThemeBlock
        themeKey="DATA:TIME"
        themeLabel="Data × Time"
        signals={MOCK_SIGNALS}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Data × Time")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders all signal lines when expanded (default)", () => {
    render(
      <SignalThemeBlock
        themeKey="DATA:TIME"
        themeLabel="Data × Time"
        signals={MOCK_SIGNALS}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText(/Pain A/)).toBeInTheDocument();
    expect(screen.getByText(/Obj B/)).toBeInTheDocument();
    expect(screen.getByText(/Impact C/)).toBeInTheDocument();
  });

  it("collapses signal lines on header click", () => {
    render(
      <SignalThemeBlock
        themeKey="DATA:TIME"
        themeLabel="Data × Time"
        signals={MOCK_SIGNALS}
        onSelect={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("Data × Time"));

    const collapse = screen.getByText(/Pain A/).closest(".MuiCollapse-root");
    expect(collapse).toHaveStyle({ height: "0px" });
  });

  it("re-expands on second header click (toggle cycle)", () => {
    render(
      <SignalThemeBlock
        themeKey="DATA:TIME"
        themeLabel="Data × Time"
        signals={MOCK_SIGNALS}
        onSelect={vi.fn()}
      />,
    );

    // Collapse then expand — signals should still be in the DOM
    fireEvent.click(screen.getByText("Data × Time"));
    fireEvent.click(screen.getByText("Data × Time"));

    expect(screen.getByText(/Pain A/)).toBeInTheDocument();
    expect(screen.getByText(/Obj B/)).toBeInTheDocument();
  });

  it("starts collapsed when defaultExpanded=false", () => {
    render(
      <SignalThemeBlock
        themeKey="DATA:TIME"
        themeLabel="Data × Time"
        signals={MOCK_SIGNALS}
        onSelect={vi.fn()}
        defaultExpanded={false}
      />,
    );

    const collapse = screen.getByText(/Pain A/).closest(".MuiCollapse-root");
    expect(collapse).toHaveStyle({ height: "0px" });
  });

  it("forwards onSelect to SignalCompactLine", () => {
    const onSelect = vi.fn();
    render(
      <SignalThemeBlock
        themeKey="DATA:TIME"
        themeLabel="Data × Time"
        signals={MOCK_SIGNALS}
        onSelect={onSelect}
      />,
    );

    fireEvent.click(screen.getByText(/Pain A/));
    expect(onSelect).toHaveBeenCalled();
  });
});

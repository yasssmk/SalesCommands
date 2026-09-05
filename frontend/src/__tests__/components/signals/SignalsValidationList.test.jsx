// frontend/src/__tests__/components/signals/SignalsValidationList.test.jsx
//
// SIG-2 — the flat signal VALIDATION list: 3 stacked status sections
// (To validate / Validated / Rejected), each grouping its signals BY TYPE
// behind a coloured SignalTypeHeader, each signal a SignalLine (no type pill —
// the type is carried by the group header). Row click opens the drawer.

import { render, screen, fireEvent, within, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

import AphoriqTheme from "../../_utils/aphoriqTheme";
import SignalsValidationList from "components/signals/SignalsValidationList";

afterEach(() => cleanup());

const SIGNALS = [
  { id: "o1", status: "PENDING", summary: "Cut onboarding time", _signalType: "objective" },
  { id: "p1", status: "PENDING", summary: "Manual exports are slow", _signalType: "pain" },
  { id: "p2", status: "PENDING", summary: "Reporting is painful", _signalType: "pain" },
  { id: "i1", status: "VALIDATED", summary: "20h/week lost", _signalType: "impact" },
  { id: "b1", status: "REJECTED", summary: "Legal will block us", _signalType: "blockers" },
];

function renderList(props = {}) {
  return render(
    <AphoriqTheme>
      <SignalsValidationList signals={SIGNALS} onSelect={vi.fn()} {...props} />
    </AphoriqTheme>,
  );
}

describe("SignalsValidationList (SIG-2)", () => {
  it("renders the 3 status sections in order: To validate → Validated → Rejected", () => {
    renderList();
    const titles = screen
      .getAllByTestId("signal-section-title")
      .map((el) => el.textContent);
    expect(titles).toEqual(["To validate", "Validated", "Rejected"]);
  });

  it("groups each section by type behind a SignalTypeHeader (type appears once per group)", () => {
    renderList();
    // Two pain signals in "To validate" → the "Pain" header shows exactly once.
    expect(screen.getAllByText("Pain")).toHaveLength(1);
    // Objective is grouped and ordered before Pain (stable type order).
    const headers = screen
      .getAllByTestId("signal-type-header")
      .map((el) => el.textContent);
    expect(headers.slice(0, 2)).toEqual(["Objective", "Pain"]);
  });

  it("renders every signal as a SignalLine row without a type pill", () => {
    renderList();
    expect(screen.getAllByTestId("signal-line")).toHaveLength(5);
    // showTypeChip is off → the type is carried by the group header only, so it
    // is never repeated as a per-row pill ("Pain" appears once, in the header).
    expect(screen.getAllByText("Pain")).toHaveLength(1);
    expect(screen.getAllByText("Objective")).toHaveLength(1);
  });

  it("opens the drawer via onSelect when a row is clicked", () => {
    const onSelect = vi.fn();
    renderList({ onSelect });
    fireEvent.click(screen.getAllByTestId("signal-line")[0]);
    expect(onSelect).toHaveBeenCalledTimes(1);
    // first row is the objective (type order), passed with its slug
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: "o1" }),
      "objective",
    );
  });

  it("hides empty Validated / Rejected sections but always shows 'To validate'", () => {
    render(
      <AphoriqTheme>
        <SignalsValidationList
          signals={[
            { id: "p1", status: "PENDING", summary: "only pending", _signalType: "pain" },
          ]}
          onSelect={vi.fn()}
        />
      </AphoriqTheme>,
    );
    const titles = screen
      .getAllByTestId("signal-section-title")
      .map((el) => el.textContent);
    expect(titles).toEqual(["To validate"]);
  });

  it("shows a 'nothing to validate' empty state when there is no pending signal", () => {
    render(
      <AphoriqTheme>
        <SignalsValidationList
          signals={[
            { id: "i1", status: "VALIDATED", summary: "done", _signalType: "impact" },
          ]}
          onSelect={vi.fn()}
        />
      </AphoriqTheme>,
    );
    const toValidate = screen.getByTestId("signal-section-to-validate");
    expect(within(toValidate).getByText(/nothing to validate/i)).toBeInTheDocument();
  });

  it("shows the empty message when there are no signals at all", () => {
    render(
      <AphoriqTheme>
        <SignalsValidationList signals={[]} onSelect={vi.fn()} emptyMessage="No signals" />
      </AphoriqTheme>,
    );
    expect(screen.getByText("No signals")).toBeInTheDocument();
    expect(screen.queryAllByTestId("signal-section-title")).toHaveLength(0);
  });

  it("shows a spinner while loading", () => {
    render(
      <AphoriqTheme>
        <SignalsValidationList signals={[]} onSelect={vi.fn()} loading />
      </AphoriqTheme>,
    );
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });
});

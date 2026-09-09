// frontend/src/__tests__/components/signals/SignalsValidationList.test.jsx
//
// SIG-2 / SIG-2-fix2 — the flat signal VALIDATION list: 3 stacked status
// sections (To validate / Validated / Rejected), each a collapsible strip with a
// STATUS-coloured title; inside, signals are grouped by TYPE, each group a
// collapsible strip with the SIG-1 type-coloured title; each signal a SignalLine
// with no chips (type / scope / nature / status all off — detail lives in the
// drawer). Default: "To validate" open, "Validated" + "Rejected" collapsed.

import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";

import AphoriqTheme, { testTheme } from "../../_utils/aphoriqTheme";
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

const follows = (a, b) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

describe("SignalsValidationList (SIG-2-fix2)", () => {
  it("renders the 3 status section headers in order", () => {
    renderList();
    const toV = screen.getByText("To validate");
    const val = screen.getByText("Validated");
    const rej = screen.getByText("Rejected");
    expect(follows(toV, val)).toBe(true);
    expect(follows(val, rej)).toBe(true);
  });

  it("P2: hides the 'To validate' section when there are 0 pending signals", () => {
    renderList({
      signals: [
        { id: "v1", status: "VALIDATED", summary: "done", _signalType: "objective" },
        { id: "r1", status: "REJECTED", summary: "nope", _signalType: "blockers" },
      ],
    });
    // No pending → the always-on exception is gone, "To validate" disappears…
    expect(screen.queryByText("To validate")).not.toBeInTheDocument();
    // …while the non-empty Validated / Rejected sections remain.
    expect(screen.getByText("Validated")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("colours each section title by STATUS (warning / success / error)", () => {
    renderList();
    expect(screen.getByText("To validate")).toHaveStyle({
      color: testTheme.palette.warning.main,
    });
    expect(screen.getByText("Validated")).toHaveStyle({
      color: testTheme.palette.success.main,
    });
    expect(screen.getByText("Rejected")).toHaveStyle({
      color: testTheme.palette.error.main,
    });
  });

  it("colours each section's count (meta) by its status", () => {
    render(
      <AphoriqTheme>
        <SignalsValidationList
          signals={[
            { id: "p1", status: "PENDING", summary: "a", _signalType: "pain" },
            { id: "p2", status: "PENDING", summary: "b", _signalType: "pain" },
            { id: "v1", status: "VALIDATED", summary: "c", _signalType: "objective" },
            { id: "v2", status: "VALIDATED", summary: "d", _signalType: "objective" },
            { id: "v3", status: "VALIDATED", summary: "e", _signalType: "objective" },
            { id: "r1", status: "REJECTED", summary: "f", _signalType: "blockers" },
            { id: "r2", status: "REJECTED", summary: "g", _signalType: "blockers" },
            { id: "r3", status: "REJECTED", summary: "h", _signalType: "blockers" },
            { id: "r4", status: "REJECTED", summary: "i", _signalType: "blockers" },
          ]}
          onSelect={vi.fn()}
        />
      </AphoriqTheme>,
    );
    // Section counts are 2 / 3 / 4 (distinct) → coloured by status.
    expect(screen.getByText("2")).toHaveStyle({ color: testTheme.palette.warning.main });
    expect(screen.getByText("3")).toHaveStyle({ color: testTheme.palette.success.main });
    expect(screen.getByText("4")).toHaveStyle({ color: testTheme.palette.error.main });
  });

  it("renders type headers in ONE uniform muted colour (not per-type colours)", () => {
    renderList();
    // Objective and Pain headers (in the open 'To validate' section) are muted…
    expect(screen.getByText("Objective")).toHaveStyle({
      color: testTheme.palette.text.secondary,
    });
    expect(screen.getByText("Pain")).toHaveStyle({
      color: testTheme.palette.text.secondary,
    });
  });

  it("defaults to 'To validate' OPEN, 'Validated' + 'Rejected' COLLAPSED", () => {
    renderList();
    // Pending rows (To validate) are visible…
    expect(screen.getByText("Manual exports are slow")).toBeInTheDocument();
    // …validated / rejected bodies are collapsed (unmounted).
    expect(screen.queryByText("20h/week lost")).not.toBeInTheDocument();
    expect(screen.queryByText("Legal will block us")).not.toBeInTheDocument();
  });

  it("expanding a collapsed section reveals its rows", async () => {
    renderList();
    fireEvent.click(screen.getByText("Validated"));
    expect(await screen.findByText("20h/week lost")).toBeInTheDocument();
  });

  it("groups each section by type, once per type, in stable order (Objective before Pain)", () => {
    renderList();
    expect(screen.getAllByText("Objective")).toHaveLength(1);
    expect(screen.getAllByText("Pain")).toHaveLength(1);
    expect(follows(screen.getByText("Objective"), screen.getByText("Pain"))).toBe(true);
  });

  it("collapses ONLY at the status-section level — type groups are plain headers", () => {
    renderList();
    // SIGNALS has all 3 statuses → exactly 3 collapsible headers (the sections).
    // If type groups were still collapsible strips there would be more.
    expect(document.querySelectorAll("[aria-expanded]")).toHaveLength(3);
    // Clicking a type header does NOT collapse its rows (no chevron / no toggle).
    fireEvent.click(screen.getByText("Pain"));
    expect(screen.getByText("Manual exports are slow")).toBeInTheDocument();
  });

  it("renders rows with NO chip (type / scope / nature / status all off)", () => {
    render(
      <AphoriqTheme>
        <SignalsValidationList
          signals={[
            {
              id: "cn1",
              status: "PENDING",
              summary: "Data must stay on-prem",
              _signalType: "constraints",
              nature_display: "Security",
              target_department: { id: "d2", name: "IT" },
            },
          ]}
          onSelect={vi.fn()}
        />
      </AphoriqTheme>,
    );
    const row = screen.getByTestId("signal-line");
    expect(screen.getByText("Data must stay on-prem")).toBeInTheDocument();
    // The signal scope is NOT shown on the row at all (neither chip nor text).
    expect(screen.queryByText(/Department · IT/)).not.toBeInTheDocument();
    expect(screen.queryByText("Business")).not.toBeInTheDocument();
    // …and there is NO chip in the row (nature "Security" + status "Pending" gone).
    expect(row.querySelector(".MuiChip-root")).toBeNull();
    expect(screen.queryByText("Security")).not.toBeInTheDocument();
    expect(screen.queryByText("Pending")).not.toBeInTheDocument();
  });

  it("does not render the +N contact-overflow chip in the list rows", () => {
    render(
      <AphoriqTheme>
        <SignalsValidationList
          signals={[
            {
              id: "p1",
              status: "PENDING",
              summary: "multi-contact pain",
              _signalType: "pain",
              source_context: {
                contacts: [
                  { id: "c1", first_name: "Dana", last_name: "Lee" },
                  { id: "c2", first_name: "Sam", last_name: "Roe" },
                  { id: "c3", first_name: "Kim", last_name: "Fox" },
                ],
              },
            },
          ]}
          onSelect={vi.fn()}
        />
      </AphoriqTheme>,
    );
    expect(screen.getByText("multi-contact pain")).toBeInTheDocument();
    // The first contact still shows as muted text, but the "+2" overflow chip is gone.
    expect(screen.queryByText("+2")).not.toBeInTheDocument();
  });

  it("opens the drawer via onSelect when a row is clicked", () => {
    const onSelect = vi.fn();
    renderList({ onSelect });
    fireEvent.click(screen.getByText("Cut onboarding time"));
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
    expect(screen.getByText("To validate")).toBeInTheDocument();
    expect(screen.queryByText("Validated")).not.toBeInTheDocument();
    expect(screen.queryByText("Rejected")).not.toBeInTheDocument();
  });

  it("P2: with 0 pending, the 'To validate' section is hidden entirely (no empty state)", () => {
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
    // The section — and its former "Nothing to validate" placeholder — are gone…
    expect(screen.queryByText("To validate")).not.toBeInTheDocument();
    expect(screen.queryByText(/nothing to validate/i)).not.toBeInTheDocument();
    // …only the non-empty Validated section remains.
    expect(screen.getByText("Validated")).toBeInTheDocument();
  });

  it("shows the empty message when there are no signals at all", () => {
    render(
      <AphoriqTheme>
        <SignalsValidationList signals={[]} onSelect={vi.fn()} emptyMessage="No signals" />
      </AphoriqTheme>,
    );
    expect(screen.getByText("No signals")).toBeInTheDocument();
    expect(screen.queryByText("To validate")).not.toBeInTheDocument();
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

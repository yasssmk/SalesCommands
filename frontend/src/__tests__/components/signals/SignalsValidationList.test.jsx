// frontend/src/__tests__/components/signals/SignalsValidationList.test.jsx
//
// SIG-2 / SIG-2-fix2 — the flat signal VALIDATION list: 3 stacked status
// sections (To validate / Validated / Rejected), each a collapsible strip with a
// STATUS-coloured title; inside, signals are grouped by TYPE, each group a
// collapsible strip with the SIG-1 type-coloured title; each signal a SignalLine
// with no chips (type / scope / nature / status all off — detail lives in the
// drawer). Default: "To validate" open, "Validated" + "Rejected" collapsed.

import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
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

  it("colours each section title by STATUS (To validate = warning, Validated = success)", () => {
    renderList();
    expect(screen.getByText("To validate")).toHaveStyle({
      color: testTheme.palette.warning.main,
    });
    expect(screen.getByText("Validated")).toHaveStyle({
      color: testTheme.palette.success.main,
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

  it("makes each TYPE group collapsible (clicking its header hides its rows)", async () => {
    renderList();
    expect(screen.getByText("Manual exports are slow")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Pain"));
    await waitFor(() =>
      expect(screen.queryByText("Manual exports are slow")).not.toBeInTheDocument(),
    );
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
    // Scope stays as muted text…
    expect(screen.getByText(/Department · IT/)).toBeInTheDocument();
    // …and there is NO chip in the row (nature "Security" + status "Pending" gone).
    expect(row.querySelector(".MuiChip-root")).toBeNull();
    expect(screen.queryByText("Security")).not.toBeInTheDocument();
    expect(screen.queryByText("Pending")).not.toBeInTheDocument();
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
    expect(screen.getByText(/nothing to validate/i)).toBeInTheDocument();
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

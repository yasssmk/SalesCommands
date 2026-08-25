// frontend/src/__tests__/signals/SignalLine.test.jsx
//
// B1: the unified compact "signal line" used by the three FLAT surfaces.
// One component renders every signal type from the raw list payload
// (tagged with _signalType). Clicking the row opens the existing signal
// drawer; the action buttons stay isolated from that click.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalLine from "components/signals/SignalLine";

afterEach(() => cleanup());

const DEPT_PAIN = {
  id: "p1",
  status: "PENDING",
  what: "DATA",
  dimension: "QUALITY",
  summary: "Marketing data is unreliable",
  scope_level: "DEPARTMENT",
  target_department: { id: "d1", name: "Marketing" },
  created_at: "2026-05-01T10:00:00Z",
  source_context: {
    activity: { id: "a1", subject: "Discovery call" },
    contacts: [
      { id: "c1", first_name: "Dana", last_name: "Lee", job_title: "CMO", department: { id: "d1", name: "Marketing" } },
    ],
  },
};

const BUSINESS_PAIN = {
  id: "p2",
  status: "PENDING",
  what: "OPS",
  dimension: "TIME",
  summary: "Company-wide reporting is slow",
  scope_level: "BUSINESS",
  created_at: "2026-05-01T10:00:00Z",
  source_context: { contacts: [] },
};

const TECH = {
  id: "t1",
  status: "PENDING",
  tech_name: "Salesforce",
  created_at: "2026-05-01T10:00:00Z",
  source_context: { contacts: [] },
};

const REJECTED_BLOCKER = {
  id: "b1",
  status: "REJECTED",
  summary: "Budget frozen",
  created_at: "2026-05-01T10:00:00Z",
  source_context: { contacts: [] },
};

// PENDING objective missing scope_level → validation reports a missing field.
const INCOMPLETE_OBJECTIVE = {
  id: "o1",
  status: "PENDING",
  what: "OPS",
  dimension: "TIME",
  summary: "Cut reporting time",
  // scope_level intentionally absent
  created_at: "2026-05-01T10:00:00Z",
  source_context: { contacts: [] },
};

const MULTI_CONTACT_PAIN = {
  ...DEPT_PAIN,
  id: "p3",
  source_context: {
    contacts: [
      { id: "c1", first_name: "Dana", last_name: "Lee", job_title: "CMO", department: { id: "d1", name: "Marketing" } },
      { id: "c2", first_name: "Sam", last_name: "Roe" },
      { id: "c3", first_name: "Kim", last_name: "Fox" },
    ],
  },
};

describe("SignalLine", () => {
  it("renders a DEPARTMENT scope chip with the target department name", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" />);
    expect(screen.getByText(/Department · Marketing/)).toBeInTheDocument();
    expect(screen.getByText("Marketing data is unreliable")).toBeInTheDocument();
  });

  it("renders a Business scope chip for a BUSINESS-scoped pain", () => {
    render(<SignalLine signal={BUSINESS_PAIN} signalType="pain" />);
    expect(screen.getByText("Business")).toBeInTheDocument();
  });

  it("renders tech_name as the message and NO scope chip for tech-stack", () => {
    render(<SignalLine signal={TECH} signalType="tech-stack" />);
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.queryByText("Business")).not.toBeInTheDocument();
    expect(screen.queryByText(/Department ·/)).not.toBeInTheDocument();
  });

  it("shows Reopen and hides Validate/Reject for a REJECTED signal", () => {
    render(
      <SignalLine
        signal={REJECTED_BLOCKER}
        signalType="blockers"
        onReopen={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /reopen/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
  });

  it("disables Validate when required fields are missing", () => {
    render(
      <SignalLine
        signal={INCOMPLETE_OBJECTIVE}
        signalType="objective"
        onValidate={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /validate/i })).toBeDisabled();
  });

  it("enables Validate for a complete PENDING signal", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" onValidate={vi.fn()} />);
    expect(screen.getByRole("button", { name: /validate/i })).toBeEnabled();
  });

  it("shows +N when the origin activity has more than one contact", () => {
    render(<SignalLine signal={MULTI_CONTACT_PAIN} signalType="pain" />);
    expect(screen.getByText(/Dana Lee/)).toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
  });

  it("opens the drawer (calls onSelect) when the row is clicked", () => {
    const onSelect = vi.fn();
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId("signal-line"));
    expect(onSelect).toHaveBeenCalledWith(DEPT_PAIN, "pain");
  });

  it("does NOT open the drawer when an action button is clicked", () => {
    const onSelect = vi.fn();
    const onValidate = vi.fn();
    render(
      <SignalLine
        signal={DEPT_PAIN}
        signalType="pain"
        onSelect={onSelect}
        onValidate={onValidate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(onValidate).toHaveBeenCalledWith(DEPT_PAIN, "pain");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("has no Delete action", () => {
    render(
      <SignalLine signal={DEPT_PAIN} signalType="pain" onValidate={vi.fn()} onReject={vi.fn()} onEdit={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("renders on two rows: chips + message on row 1, date/contact/actions on row 2", () => {
    render(
      <SignalLine signal={DEPT_PAIN} signalType="pain" onValidate={vi.fn()} onReject={vi.fn()} onEdit={vi.fn()} />,
    );
    const line = screen.getByTestId("signal-line");
    // The line is a two-row column: exactly two direct children (row 1, row 2).
    expect(line.children).toHaveLength(2);

    const [row1, row2] = line.children;
    // Row 1 carries the message.
    expect(row1).toHaveTextContent("Marketing data is unreliable");
    // Row 2 carries the origin contact + date + the actions.
    expect(row2).toHaveTextContent("Dana Lee");
    expect(row2).toHaveTextContent(/2026/);
    expect(row2.querySelector("button")).toBeTruthy();
  });
});

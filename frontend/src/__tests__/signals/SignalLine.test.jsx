// frontend/src/__tests__/signals/SignalLine.test.jsx
//
// C2: the unified compact "signal line" is INFORMATIONAL ONLY. It renders
// every signal type from the raw list payload (tagged with _signalType),
// shows status + message + meta, and is clickable to open the signal drawer.
// It carries NO lifecycle action buttons — validate / reject / edit / reopen
// all live inside the drawer now.

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

describe("SignalLine — informational content", () => {
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

  it("shows +N when the origin activity has more than one contact", () => {
    render(<SignalLine signal={MULTI_CONTACT_PAIN} signalType="pain" />);
    expect(screen.getByText(/Dana Lee/)).toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
  });
});

describe("SignalLine — no action buttons (actions live in the drawer)", () => {
  // The row is purely informational: it must render NO lifecycle action
  // button for any status, even when legacy action handlers are still
  // passed by a not-yet-cleaned parent (extra props are ignored).
  it("renders no validate / reject / edit / reopen / delete button on a PENDING row", () => {
    render(
      <SignalLine
        signal={DEPT_PAIN}
        signalType="pain"
        onValidate={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onReopen={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("renders no Reopen button on a REJECTED row (reopen lives in the drawer)", () => {
    render(
      <SignalLine
        signal={REJECTED_BLOCKER}
        signalType="blockers"
        onReopen={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();
  });

  it("the row itself is the only interactive element (no nested action buttons)", () => {
    const { container } = render(
      <SignalLine signal={DEPT_PAIN} signalType="pain" onSelect={vi.fn()} />,
    );
    // The clickable row uses role="button" on the container; there are no
    // <button> children inside it.
    expect(screen.getByTestId("signal-line")).toHaveAttribute("role", "button");
    expect(container.querySelector("button")).toBeNull();
  });
});

describe("SignalLine — click opens the drawer", () => {
  it("calls onSelect with (signal, type) when the row is clicked", () => {
    const onSelect = vi.fn();
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId("signal-line"));
    expect(onSelect).toHaveBeenCalledWith(DEPT_PAIN, "pain");
  });

  it("calls onSelect on keyboard activation (Enter)", () => {
    const onSelect = vi.fn();
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" onSelect={onSelect} />);
    fireEvent.keyDown(screen.getByTestId("signal-line"), { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(DEPT_PAIN, "pain");
  });
});

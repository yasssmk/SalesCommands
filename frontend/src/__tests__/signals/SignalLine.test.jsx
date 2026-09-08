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

const CONSTRAINT = {
  id: "cn1",
  status: "PENDING",
  summary: "Data must stay on-prem",
  nature_display: "Security",
  target_department: { id: "d2", name: "IT" },
  created_at: "2026-05-01T10:00:00Z",
  source_context: { contacts: [] },
};

describe("SignalLine — nature & status chip toggles", () => {
  it("renders the nature chip by DEFAULT for a constraint (DC/Account unchanged)", () => {
    render(<SignalLine signal={CONSTRAINT} signalType="constraints" />);
    expect(screen.getByText("Security")).toBeInTheDocument();
  });

  it("hides the nature chip when showNatureChip=false", () => {
    render(<SignalLine signal={CONSTRAINT} signalType="constraints" showNatureChip={false} />);
    expect(screen.queryByText("Security")).not.toBeInTheDocument();
  });

  it("renders the status chip by DEFAULT (DC/Account unchanged)", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("hides the status chip when showStatusChip=false", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" showStatusChip={false} />);
    expect(screen.queryByText("Pending")).not.toBeInTheDocument();
  });
});

const COMPETITOR = {
  id: "cp1",
  status: "PENDING",
  competitor_name: "Salesforce",
  // The narrative summary carries a technical prefix — it must NOT be the row text.
  summary: "competitor: Salesforce",
  created_at: "2026-05-01T10:00:00Z",
  source_context: { contacts: [] },
};

describe("SignalLine — competitor message", () => {
  it("renders the competitor NAME alone, not the 'competitor:' summary prefix", () => {
    render(<SignalLine signal={COMPETITOR} signalType="competitors" showTypeChip={false} />);
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.queryByText(/competitor:/i)).not.toBeInTheDocument();
  });
});

describe("SignalLine — inline validate/reject actions (SIG-3)", () => {
  it("renders NO action buttons by default (DC/Account unchanged)", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" />);
    expect(screen.queryByRole("button", { name: /validate signal/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject signal/i })).not.toBeInTheDocument();
  });

  it("renders ✓ Validate and ✗ Reject on a PENDING row when handlers are provided", () => {
    render(
      <SignalLine signal={DEPT_PAIN} signalType="pain" onValidate={vi.fn()} onReject={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /validate signal/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject signal/i })).toBeInTheDocument();
  });

  it("shows NO inline actions on a non-pending row (validated/rejected are done)", () => {
    const validated = { ...DEPT_PAIN, status: "VALIDATED" };
    render(
      <SignalLine signal={validated} signalType="pain" onValidate={vi.fn()} onReject={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /validate signal/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject signal/i })).not.toBeInTheDocument();
  });

  it("clicking ✓ calls onValidate(signal, type) and NOT onSelect (stopPropagation)", () => {
    const onValidate = vi.fn();
    const onSelect = vi.fn();
    render(
      <SignalLine
        signal={DEPT_PAIN}
        signalType="pain"
        onValidate={onValidate}
        onReject={vi.fn()}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /validate signal/i }));
    expect(onValidate).toHaveBeenCalledWith(DEPT_PAIN, "pain");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("clicking ✗ calls onReject(signal, type) and NOT onSelect", () => {
    const onReject = vi.fn();
    const onSelect = vi.fn();
    render(
      <SignalLine
        signal={DEPT_PAIN}
        signalType="pain"
        onValidate={vi.fn()}
        onReject={onReject}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /reject signal/i }));
    expect(onReject).toHaveBeenCalledWith(DEPT_PAIN, "pain");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("clicking the message (not the actions) still opens the drawer via onSelect", () => {
    const onSelect = vi.fn();
    render(
      <SignalLine
        signal={DEPT_PAIN}
        signalType="pain"
        onValidate={vi.fn()}
        onReject={vi.fn()}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("Marketing data is unreliable"));
    expect(onSelect).toHaveBeenCalledWith(DEPT_PAIN, "pain");
  });
});

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

  it("renders the scope as an outlined chip by DEFAULT (DC/Account unchanged)", () => {
    const { container } = render(<SignalLine signal={DEPT_PAIN} signalType="pain" />);
    const scopeChip = [...container.querySelectorAll(".MuiChip-outlined")].find(
      (c) => /Department · Marketing/.test(c.textContent),
    );
    expect(scopeChip).toBeTruthy();
  });

  it("renders NO signal scope (neither chip nor text) when showScopeChip=false, keeping the contact identity", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" showScopeChip={false} />);
    // The signal scope is gone entirely — no "Department · …" scope, no "Business".
    expect(screen.queryByText(/Department · Marketing/)).not.toBeInTheDocument();
    expect(screen.queryByText("Business")).not.toBeInTheDocument();
    // The CONTACT identity stays — SIG-5f: name bold/primary, job · dept muted.
    const name = screen.getByText("Dana Lee");
    const meta = screen.getByText(/CMO · Marketing/);
    expect(getComputedStyle(name).fontWeight).toBe("600");
    expect(getComputedStyle(name).color).toBe("rgba(0, 0, 0, 0.87)"); // text.primary
    expect(getComputedStyle(meta).color).toBe("rgba(0, 0, 0, 0.6)"); // text.secondary (muted)
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

  it("hides the +N contact-overflow chip when showContactOverflow=false", () => {
    render(<SignalLine signal={MULTI_CONTACT_PAIN} signalType="pain" showContactOverflow={false} />);
    // The first contact still shows…
    expect(screen.getByText(/Dana Lee/)).toBeInTheDocument();
    // …but the "+2" overflow chip is gone.
    expect(screen.queryByText("+2")).not.toBeInTheDocument();
  });
});

describe("SignalLine — no action buttons (actions live in the drawer)", () => {
  // The row is purely informational: it must render NO lifecycle action
  // button for any status, even when legacy action handlers are still
  // passed by a not-yet-cleaned parent (extra props are ignored).
  it("renders no edit / reopen / delete button inline (those live in the drawer)", () => {
    // edit / reopen are ignored inline (drawer-only); validate/reject are inline
    // only when their handlers are wired (SIG-3) — none here → no buttons at all.
    render(
      <SignalLine
        signal={DEPT_PAIN}
        signalType="pain"
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

describe("SignalLine — visual polish (C-polish)", () => {
  it("shows the type chip by default (flat views: the only type cue)", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" />);
    // DEPT_PAIN's message has no "Pain" text, so this matches the type chip.
    expect(screen.getByText("Pain")).toBeInTheDocument();
  });

  it("hides the type chip when showTypeChip=false (grouped, type in header)", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" showTypeChip={false} />);
    expect(screen.queryByText("Pain")).not.toBeInTheDocument();
  });

  it("renders the full message with no truncation (no noWrap clamp)", () => {
    const long = {
      ...BUSINESS_PAIN,
      summary:
        "Consolidating the weekly report across five spreadsheets takes the ops team about five hours every single week and delays the Monday review.",
    };
    render(<SignalLine signal={long} signalType="pain" />);
    const msg = screen.getByText(long.summary);
    expect(msg).toBeInTheDocument();
    // The old ellipsis clamp added the MuiTypography-noWrap class — gone now.
    expect(msg.className).not.toMatch(/noWrap/);
  });

  it("puts the scope on the meta line (line 2), not before the message (line 1)", () => {
    render(<SignalLine signal={DEPT_PAIN} signalType="pain" />);
    const row = screen.getByTestId("signal-line");
    // The row now wraps its two lines in a content column (actions sit beside it).
    const content = row.children[0];
    const [line1, line2] = content.children;
    expect(line1).not.toHaveTextContent(/Department · Marketing/);
    expect(line2).toHaveTextContent(/Department · Marketing/);
  });

  it("renders the status with the light DS treatment (not the old solid chip)", () => {
    const { container } = render(<SignalLine signal={DEPT_PAIN} signalType="pain" />);
    // The DS light variant adds the MuiChip-light class.
    const lightChips = container.querySelectorAll(".MuiChip-light");
    expect(lightChips.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Pending")).toBeInTheDocument();
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

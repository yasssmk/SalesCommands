// frontend/src/__tests__/components/signals/SignalDetailPanel.test.jsx
//
// B3.5.3 — SignalDetailPanel is the signal DETAIL dé-coqué: the shared
// SignalDetailContent plus origin-activity navigation, injected into the single
// workspace drawer coque via openDrawer (no <Drawer> shell of its own; the coque
// owns the close button). These tests exercise the panel's rendering + lifecycle
// actions directly (no coque needed — useWorkspaceDrawer falls back to a no-op
// context when unwrapped; next/navigation is globally mocked in vitest.setup.js).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { useRouter } from "next/navigation";
import SignalDetailPanel from "components/signals/SignalDetailPanel";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const MOCK_PAIN = {
  id: "s1",
  status: "PENDING",
  summary: "Lost 5h/week on consolidation",
  what: "DATA",
  dimension: "TIME",
  what_display: "Data",
  dimension_display: "Time",
  scope_level_display: "Business",
  source_quote: "We lose about 5 hours per week just consolidating reports",
  notes: "Critical for Q3",
  created_at: "2026-05-12T14:32:00Z",
  source: "LLM_EXTRACTED",
  contact: null,
  source_context: {
    contacts: [{ id: "c1", first_name: "Pierre", last_name: "Dupont" }],
  },
  related_techstack_mention: "Excel",
};

const MOCK_TECHSTACK = {
  id: "ts1",
  status: "PENDING",
  summary: null,
  tech_name: "Salesforce",
  is_competitor: true,
  is_integration: false,
  is_to_replace: false,
  metadata: {},
  usage_scope_display: "Company-wide",
  usage_start_year: 2022,
  renewal_date: "2026-06-15",
  cost_description: "~50k/year",
  is_discontinued: false,
  notes: "Main CRM tool",
  source_quote: "Nous utilisons Salesforce depuis 2 ans",
  contact: null,
  source_context: {
    contacts: [{ id: "c2", first_name: "Jane", last_name: "Doe" }],
  },
};

const MOCK_OBJECTIVE = {
  id: "o1",
  status: "VALIDATED",
  summary: "Reduce reporting time by 50%",
  what_display: "Operations",
  dimension_display: "Time",
  scope_level: "DEPARTMENT",
  scope_level_display: "Department",
  success_criteria: "Monthly reports done in 2 hours",
  target_date: "2026-12-31",
  target_contact: { id: "c3", first_name: "Marc", last_name: "Leblanc" },
  target_department: { id: "d1", name: "Finance" },
  notes: "Priority for VP",
  source_quote: "We want to cut reporting time by half",
  validated_by: { first_name: "Admin", last_name: "User" },
  validated_at: "2026-06-01T10:00:00Z",
  contact: null,
  source_context: { contacts: [] },
};

const MOCK_BLOCKER = {
  id: "b1",
  status: "PENDING",
  summary: "Budget frozen until Q2",
  source_quote: "Our budget is completely frozen",
  contact: { id: "c4", first_name: "Sophie", last_name: "Martin" },
};

const MOCK_IMPACT = {
  id: "i1",
  status: "PENDING",
  summary: "5h/week lost on manual consolidation",
  what_display: "Operations",
  dimension_display: "Time",
  impact_type_display: "Time impact",
  scope_level_display: "Business",
  metric_text: "5 hours per week",
  human_impact_display: "Frustration",
  source_quote: "We spend 5 hours every week",
  contact: null,
  source_context: { contacts: [] },
};

const MOCK_NEXTSTEP = {
  id: "ns1",
  status: "PENDING",
  suggested_title: "Follow up on pricing",
  suggested_activity_type_display: "Phone Call",
  suggested_due_date: "2026-06-15",
  suggested_contacts: [
    { id: "c5", first_name: "Jane", last_name: "Doe" },
  ],
  source_quote: "We should discuss pricing next week",
  linked_activity: null,
};

describe("SignalDetailPanel", () => {
  // === Rendering + header ===

  it("renders signal details", () => {
    render(<SignalDetailPanel signal={MOCK_PAIN} signalType="pain" />);

    expect(screen.getByText("Pain")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText(/Lost 5h\/week/)).toBeInTheDocument();
    expect(screen.getByText(/We lose about 5 hours/)).toBeInTheDocument();
  });

  it("shows Validate, Reject, Edit buttons for PENDING signal", () => {
    render(
      <SignalDetailPanel
        signal={MOCK_PAIN}
        signalType="pain"
        onValidate={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /validate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });

  it("hides Validate/Reject for VALIDATED signal", () => {
    const validated = { ...MOCK_PAIN, status: "VALIDATED" };
    render(
      <SignalDetailPanel signal={validated} signalType="pain" onEdit={vi.fn()} />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });

  it("hides all action buttons when locked", () => {
    render(<SignalDetailPanel signal={MOCK_PAIN} signalType="pain" isLocked />);

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
  });

  it("calls onValidate on Validate click", () => {
    const onValidate = vi.fn();
    render(
      <SignalDetailPanel signal={MOCK_PAIN} signalType="pain" onValidate={onValidate} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(onValidate).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("calls onReject on Reject click", () => {
    const onReject = vi.fn();
    render(
      <SignalDetailPanel signal={MOCK_PAIN} signalType="pain" onReject={onReject} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("calls onEdit on Edit click", () => {
    const onEdit = vi.fn();
    render(
      <SignalDetailPanel signal={MOCK_PAIN} signalType="pain" onEdit={onEdit} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(onEdit).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("returns null when signal is null", () => {
    const { container } = render(
      <SignalDetailPanel signal={null} signalType="pain" />,
    );

    expect(container.firstChild).toBeNull();
  });

  // === Enriched detail fields ===

  it("shows pain-specific fields: theme, scope, notes, related tool", () => {
    render(<SignalDetailPanel signal={MOCK_PAIN} signalType="pain" />);

    expect(screen.getByText("CLASSIFICATION")).toBeInTheDocument();
    expect(screen.getByText("Data × Time")).toBeInTheDocument();
    expect(screen.getByText("Business")).toBeInTheDocument();
    // related_techstack_mention now rendered via the shared PainDetailBlock
    expect(screen.getByText("RELATED TOOL")).toBeInTheDocument();
    expect(screen.getByText("Excel")).toBeInTheDocument();
    expect(screen.getByText("Critical for Q3")).toBeInTheDocument();
    // Pierre Dupont now appears both as the per-type Contact row and in the
    // ORIGIN provenance contact list.
    expect(screen.getAllByText("Pierre Dupont").length).toBeGreaterThanOrEqual(1);
  });

  it("shows tech-stack-specific fields: tool, qualification, scope, cost", () => {
    render(<SignalDetailPanel signal={MOCK_TECHSTACK} signalType="tech-stack" />);

    expect(screen.getByText("IDENTITY")).toBeInTheDocument();
    expect(screen.getAllByText("Salesforce").length).toBeGreaterThanOrEqual(1);
    // Usage + lifecycle rendered via the shared TechDetailBlock. The manual
    // "Competitor" tag was retired (competitors are their own signal type),
    // so a legacy is_competitor=true renders no chip and — with the other two
    // flags false — no Qualification row at all.
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    expect(screen.queryByText("Qualification")).not.toBeInTheDocument();
    expect(screen.getByText("TOOL USAGE")).toBeInTheDocument();
    expect(screen.getByText("Company-wide")).toBeInTheDocument();
    expect(screen.getByText("2022")).toBeInTheDocument();
    expect(screen.getByText("~50k/year")).toBeInTheDocument();
    expect(screen.getByText("Main CRM tool")).toBeInTheDocument();
  });

  it("shows objective-specific fields: success criteria, target date, target contact", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);

    // Objective specifics now rendered via the shared ObjectiveDetailBlock.
    // Owner line follows the card's single-truth logic: DEPARTMENT scope
    // shows "Department: {name}" (not the target contact).
    expect(screen.getByText("OBJECTIVE")).toBeInTheDocument();
    expect(screen.getByText("Monthly reports done in 2 hours")).toBeInTheDocument();
    expect(screen.getByText("Department: Finance")).toBeInTheDocument();
  });

  it("shows validated_by info for validated signals", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);

    expect(screen.getByText("Admin User")).toBeInTheDocument();
  });

  it("shows blocker-specific fields: raised by, source quote", () => {
    render(<SignalDetailPanel signal={MOCK_BLOCKER} signalType="blockers" />);

    expect(screen.getByText("Sophie Martin")).toBeInTheDocument();
    expect(screen.getByText(/Our budget is completely frozen/)).toBeInTheDocument();
  });

  it("shows impact-specific fields: impact type, metric, human impact", () => {
    render(<SignalDetailPanel signal={MOCK_IMPACT} signalType="impact" />);

    expect(screen.getByText("Time impact")).toBeInTheDocument();
    expect(screen.getByText("5 hours per week")).toBeInTheDocument();
    expect(screen.getByText("Frustration")).toBeInTheDocument();
  });

  it("shows next-step-specific fields: type, due date, contacts", () => {
    render(<SignalDetailPanel signal={MOCK_NEXTSTEP} signalType="next-steps" />);

    expect(screen.getByText("Phone Call")).toBeInTheDocument();
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
  });

  it("hides null/empty fields instead of showing N/A", () => {
    const minimal = {
      id: "m1",
      status: "PENDING",
      summary: "Minimal signal",
      contact: null,
      source_context: { contacts: [] },
    };
    render(<SignalDetailPanel signal={minimal} signalType="pain" />);

    expect(screen.queryByText("N/A")).not.toBeInTheDocument();
    expect(screen.queryByText("RELATED TOOL")).not.toBeInTheDocument();
  });

  // === Shared-block composition (B1.2.1) ===

  it("composes the shared ImpactDetailBlock (IMPACT EVIDENCE section)", () => {
    // The 'IMPACT EVIDENCE' section heading is produced ONLY by the shared
    // ImpactDetailBlock — its presence proves the panel composes the block
    // rather than keeping its own per-type copy.
    render(<SignalDetailPanel signal={MOCK_IMPACT} signalType="impact" />);
    expect(screen.getByText("IMPACT EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText("Time impact")).toBeInTheDocument();
  });

  // === ORIGIN provenance (B1) ===

  it("renders the full contact list with job_title + department in ORIGIN", () => {
    const signal = {
      id: "pd1",
      status: "PENDING",
      summary: "Dept-scoped pain",
      source_quote: "quote",
      source_context: {
        activity: { id: "act-1", subject: "Discovery call" },
        contacts: [
          { id: "c1", first_name: "Dana", last_name: "Lee", job_title: "CMO", department: { id: "d1", name: "Marketing" } },
          { id: "c2", first_name: "Sam", last_name: "Roe" },
        ],
      },
    };
    render(<SignalDetailPanel signal={signal} signalType="pain" />);
    expect(screen.getByText("ORIGIN")).toBeInTheDocument();
    expect(screen.getByText("Dana Lee · CMO · Marketing")).toBeInTheDocument();
    expect(screen.getByText("Sam Roe")).toBeInTheDocument();
  });

  it("navigates to the origin activity on 'View origin activity' click", () => {
    const push = vi.fn();
    vi.mocked(useRouter).mockReturnValue({ push });
    const signal = {
      id: "pd2",
      status: "PENDING",
      summary: "Dept-scoped pain",
      source_context: {
        activity: { id: "act-42" },
        contacts: [{ id: "c1", first_name: "Dana", last_name: "Lee" }],
      },
    };
    render(<SignalDetailPanel signal={signal} signalType="pain" />);
    fireEvent.click(screen.getByRole("button", { name: /view origin activity/i }));
    expect(push).toHaveBeenCalledWith("/activities/act-42");
  });

  it("omits ORIGIN when there is no activity id and no contacts", () => {
    const signal = {
      id: "pd3",
      status: "PENDING",
      summary: "bare",
      source_context: { contacts: [] },
    };
    render(<SignalDetailPanel signal={signal} signalType="pain" />);
    expect(screen.queryByText("ORIGIN")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /view origin activity/i }),
    ).not.toBeInTheDocument();
  });

  it("shows no qualification row when all three booleans are false", () => {
    // A tool the account simply uses — the row is omitted entirely
    // rather than rendered empty. The old "Not in catalog" chip this
    // replaces is gone with the catalogue (S10).
    const plainTech = {
      id: "pt1",
      status: "PENDING",
      tech_name: "CustomTool",
      is_competitor: false,
      is_integration: false,
      is_to_replace: false,
      source_quote: "They rely on it heavily",
      contact: null,
      source_context: { contacts: [] },
    };
    render(<SignalDetailPanel signal={plainTech} signalType="tech-stack" />);

    // Appears twice: panel header + IDENTITY row.
    expect(screen.getAllByText("CustomTool").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Qualification")).not.toBeInTheDocument();
    expect(screen.queryByText("Not in catalog")).not.toBeInTheDocument();
  });

  // === C2: all four actions live here (rows are now informational) ===

  it("shows Reopen only for a REJECTED signal, and fires onReopen", () => {
    const onReopen = vi.fn();
    const rejected = { ...MOCK_PAIN, status: "REJECTED" };
    render(
      <SignalDetailPanel
        signal={rejected}
        signalType="pain"
        onReopen={onReopen}
        onEdit={vi.fn()}
      />,
    );
    // Reopen present; validate/reject absent for a rejected signal.
    const reopen = screen.getByRole("button", { name: /reopen/i });
    expect(reopen).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();

    fireEvent.click(reopen);
    expect(onReopen).toHaveBeenCalledWith(rejected, "pain");
  });

  it("does NOT show Reopen for PENDING or VALIDATED signals", () => {
    const { rerender } = render(
      <SignalDetailPanel signal={MOCK_PAIN} signalType="pain" onReopen={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();

    rerender(
      <SignalDetailPanel signal={{ ...MOCK_PAIN, status: "VALIDATED" }} signalType="pain" onReopen={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();
  });

  it("hides Reopen when locked", () => {
    render(
      <SignalDetailPanel
        signal={{ ...MOCK_PAIN, status: "REJECTED" }}
        signalType="pain"
        onReopen={vi.fn()}
        isLocked
      />,
    );
    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();
  });

  it("disables Validate when required fields are missing (rule reused from the rows)", () => {
    // PENDING objective missing scope_level → getMissingFields reports a gap.
    const incompleteObjective = {
      id: "o-inc",
      status: "PENDING",
      summary: "Cut reporting time",
      what: "OPS",
      dimension: "TIME",
      // scope_level intentionally absent
      source_context: { contacts: [] },
    };
    render(
      <SignalDetailPanel
        signal={incompleteObjective}
        signalType="objective"
        onValidate={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /validate/i })).toBeDisabled();
  });
});

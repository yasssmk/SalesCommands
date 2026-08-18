// frontend/src/__tests__/signals/SignalQuickDrawer.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";

afterEach(() => {
  cleanup();
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
  related_techstack: {
    product_name: "Excel",
    company_name: "Microsoft",
  },
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

describe("SignalQuickDrawer", () => {
  // === Existing tests (preserved) ===

  it("renders signal details when open", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_PAIN}
        signalType="pain"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Pain")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText(/Lost 5h\/week/)).toBeInTheDocument();
    expect(screen.getByText(/We lose about 5 hours/)).toBeInTheDocument();
  });

  it("shows Validate, Reject, Edit buttons for PENDING signal", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_PAIN}
        signalType="pain"
        onClose={vi.fn()}
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
      <SignalQuickDrawer
        open={true}
        signal={validated}
        signalType="pain"
        onClose={vi.fn()}
        onEdit={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });

  it("hides all action buttons when locked", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_PAIN}
        signalType="pain"
        onClose={vi.fn()}
        isLocked
      />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
  });

  it("calls onValidate on Validate click", () => {
    const onValidate = vi.fn();
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_PAIN}
        signalType="pain"
        onClose={vi.fn()}
        onValidate={onValidate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(onValidate).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("calls onReject on Reject click", () => {
    const onReject = vi.fn();
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_PAIN}
        signalType="pain"
        onClose={vi.fn()}
        onReject={onReject}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("calls onEdit on Edit click", () => {
    const onEdit = vi.fn();
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_PAIN}
        signalType="pain"
        onClose={vi.fn()}
        onEdit={onEdit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(onEdit).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("calls onClose on close button click", () => {
    const onClose = vi.fn();
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_PAIN}
        signalType="pain"
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /close drawer/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("returns null when signal is null", () => {
    const { container } = render(
      <SignalQuickDrawer
        open={true}
        signal={null}
        signalType="pain"
        onClose={vi.fn()}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  // === New enriched drawer tests ===

  it("shows pain-specific fields: theme, scope, notes, related tool", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_PAIN}
        signalType="pain"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("CLASSIFICATION")).toBeInTheDocument();
    expect(screen.getByText("Data × Time")).toBeInTheDocument();
    expect(screen.getByText("Business")).toBeInTheDocument();
    expect(screen.getByText("RELATED TOOL")).toBeInTheDocument();
    expect(screen.getByText("Excel")).toBeInTheDocument();
    expect(screen.getByText("Microsoft")).toBeInTheDocument();
    expect(screen.getByText("Critical for Q3")).toBeInTheDocument();
    expect(screen.getByText("Pierre Dupont")).toBeInTheDocument();
  });

  it("shows tech-stack-specific fields: tool, qualification, scope, cost", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_TECHSTACK}
        signalType="tech-stack"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("IDENTITY")).toBeInTheDocument();
    expect(screen.getAllByText("Salesforce").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Qualification")).toBeInTheDocument();
    expect(screen.getAllByText("Competitor").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("USAGE")).toBeInTheDocument();
    expect(screen.getByText("Company-wide")).toBeInTheDocument();
    expect(screen.getByText("2022")).toBeInTheDocument();
    expect(screen.getByText("COST & STATUS")).toBeInTheDocument();
    expect(screen.getByText("~50k/year")).toBeInTheDocument();
    expect(screen.getByText("Main CRM tool")).toBeInTheDocument();
  });

  it("shows objective-specific fields: success criteria, target date, target contact", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_OBJECTIVE}
        signalType="objective"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("DETAILS")).toBeInTheDocument();
    expect(screen.getByText("Monthly reports done in 2 hours")).toBeInTheDocument();
    expect(screen.getByText("Marc Leblanc")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
  });

  it("shows validated_by info for validated signals", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_OBJECTIVE}
        signalType="objective"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Admin User")).toBeInTheDocument();
  });

  it("shows blocker-specific fields: raised by, source quote", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_BLOCKER}
        signalType="blockers"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Sophie Martin")).toBeInTheDocument();
    expect(screen.getByText(/Our budget is completely frozen/)).toBeInTheDocument();
  });

  it("shows impact-specific fields: impact type, metric, human impact", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_IMPACT}
        signalType="impact"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Time impact")).toBeInTheDocument();
    expect(screen.getByText("5 hours per week")).toBeInTheDocument();
    expect(screen.getByText("Frustration")).toBeInTheDocument();
  });

  it("shows next-step-specific fields: type, due date, contacts", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_NEXTSTEP}
        signalType="next-steps"
        onClose={vi.fn()}
      />,
    );

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
    render(
      <SignalQuickDrawer
        open={true}
        signal={minimal}
        signalType="pain"
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText("N/A")).not.toBeInTheDocument();
    expect(screen.queryByText("RELATED TOOL")).not.toBeInTheDocument();
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
    render(
      <SignalQuickDrawer
        open={true}
        signal={plainTech}
        signalType="tech-stack"
        onClose={vi.fn()}
      />,
    );

    // Appears twice: drawer header + IDENTITY row.
    expect(screen.getAllByText("CustomTool").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Qualification")).not.toBeInTheDocument();
    expect(screen.queryByText("Not in catalog")).not.toBeInTheDocument();
  });
});

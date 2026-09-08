// frontend/src/__tests__/components/signals/SignalDetailPanel.test.jsx
//
// B3.5.3 — SignalDetailPanel is the signal DETAIL dé-coqué: the shared
// SignalDetailContent plus origin-activity navigation, injected into the single
// workspace drawer coque via openDrawer (no <Drawer> shell of its own; the coque
// owns the close button). These tests exercise the panel's rendering + lifecycle
// actions directly (no coque needed — useWorkspaceDrawer falls back to a no-op
// context when unwrapped; next/navigation is globally mocked in vitest.setup.js).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { useRouter } from "next/navigation";
import AphoriqTheme, { testTheme } from "../../_utils/aphoriqTheme";
import SignalDetailPanel from "components/signals/SignalDetailPanel";

// The objective detail uses StatusPill (reads theme.aphoriQ) — render under the
// project theme wrapper so those tokens resolve.
const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

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
  what: "OPS",
  dimension: "TIME",
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

  it("shows objective fields in the new read layout (success criteria, scope)", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);

    // SIG-5e: read-mirror of the edit — sections + values, no ObjectiveDetailBlock.
    // SIG-5e-fix4: scope reads as a label/value row (label 'Department' / value 'Finance').
    expect(screen.getByText("Monthly reports done in 2 hours")).toBeInTheDocument();
    expect(screen.getByText("Department")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
  });

  // ==== SIG-5e — Objective detail rebuilt as a read mirror of the edit ====

  const OBJ_WITH_ORIGIN = {
    ...MOCK_OBJECTIVE,
    id: "o-origin",
    status: "PENDING",
    validated_by: undefined,
    validated_at: undefined,
    source_context: {
      activity: { id: "act-9" },
      contacts: [{ id: "c1", first_name: "Dana", last_name: "Lee", job_title: "CFO" }],
    },
  };

  it("SIG-5e-fix3: 4 short sections (Goal/Scope/Metrics/Source) — quote+origin merged", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    expect(screen.getByText("Goal")).toBeInTheDocument();
    expect(screen.getByText("Scope")).toBeInTheDocument();
    expect(screen.getByText("Metrics")).toBeInTheDocument();
    expect(screen.getByText("Source")).toBeInTheDocument();
    // Merged: the old separate "Source quote" and "Origin" headers are gone.
    expect(screen.queryByText("Source quote")).not.toBeInTheDocument();
    expect(screen.queryByText("Origin")).not.toBeInTheDocument();
    // No instruction subtitles; the recap conveys the axes.
    expect(
      screen.queryByText("Describe the objective and pick its canonical axes."),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Operations × Time")).toBeInTheDocument();
  });

  it("SIG-5e-fix3: title 'Objective' + status pill on the same header line", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    expect(screen.getByTestId("objective-detail-title")).toHaveTextContent("Objective");
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Validated");
  });

  it("SIG-5e-fix4: the 'Objective' title is rendered at the large (h3) heading size", () => {
    // Point 3 — the in-detail title matches the edit drawer title (coque h3
    // bold), not the previous h6. MUI maps variant h3 to an <h3> element.
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    expect(screen.getByTestId("objective-detail-title").tagName).toBe("H3");
  });

  it("SIG-5e-fix4: the summary sits in a posed background box", () => {
    // Point 4 — the summary is posed on a subtle background box so it stands
    // out, rather than being a bare paragraph.
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    expect(screen.getByTestId("objective-summary-box")).toHaveTextContent(
      "Reduce reporting time by 50%",
    );
  });

  it("SIG-5e-fix4: scope is a label/value row — 'Department' and 'Finance' are separate", () => {
    // Point 5 — scope reads as a 2-column label(left)/value(right) row, not the
    // old combined "Department: Finance" string.
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    expect(screen.getByText("Department")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
    expect(screen.queryByText("Department: Finance")).not.toBeInTheDocument();
  });

  it("SIG-5e-fix4: target date reads as a label/value row ('Target date' / value)", () => {
    // Point 6 — target date is a label(left)/value(right) row in Metrics.
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    expect(screen.getByText("Target date")).toBeInTheDocument();
    expect(screen.getByText("31 Dec 2026")).toBeInTheDocument();
  });

  it("SIG-5e-fix5: with inlineClose, title + pill + close share ONE header row", () => {
    // Point 1 — the coque cross is suppressed for the objective drawer and the
    // close (×) moves into the detail header, on the same row as title + pill.
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" inlineClose />);
    const header = screen.getByTestId("objective-detail-header");
    expect(within(header).getByTestId("objective-detail-title")).toHaveTextContent("Objective");
    expect(within(header).getByTestId("status-pill")).toBeInTheDocument();
    expect(within(header).getByRole("button", { name: /close drawer/i })).toBeInTheDocument();
  });

  it("SIG-5e-fix5: without inlineClose there is no in-header close (DC/Account unchanged)", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    const header = screen.getByTestId("objective-detail-header");
    expect(within(header).queryByRole("button", { name: /close drawer/i })).not.toBeInTheDocument();
  });

  it("SIG-5e-fix5: Goal is a single box holding summary + centered separator + axis recap", () => {
    // Point 2 — one enclosing Goal box wraps the summary, a short centered
    // separator, and the axis recap (previously two separate backgrounds).
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    const goal = screen.getByTestId("objective-goal-box");
    expect(within(goal).getByText("Reduce reporting time by 50%")).toBeInTheDocument();
    expect(within(goal).getByText("Operations × Time")).toBeInTheDocument();
    expect(within(goal).getByTestId("objective-goal-separator")).toBeInTheDocument();
  });

  it("UI-5: the Goal box uses surface.level1 — the same token as the activity header", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    const el = screen.getByTestId("objective-goal-box");
    const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
    const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
    const rule = classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
    expect(rule).toContain(`background-color:${testTheme.aphoriQ.surface.level1}`);
    // not the old ad-hoc overlay, nor level2
    expect(rule).not.toContain(testTheme.aphoriQ.surface.level2);
  });

  it("SIG-5e-fix6: canonical_key is legible — rendered in text.secondary, not disabled", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    const line = screen.getByText(/canonical_key:/);
    expect(getComputedStyle(line).color).toBe(testTheme.palette.text.secondary);
    expect(getComputedStyle(line).color).not.toBe(testTheme.palette.text.disabled);
  });

  it("SIG-5e-fix3: empty Metrics renders a single 'No metrics defined' line", () => {
    const noMetrics = { ...MOCK_OBJECTIVE, id: "o-nm", success_criteria: "", target_date: "", notes: "" };
    render(<SignalDetailPanel signal={noMetrics} signalType="objective" />);
    expect(screen.getByText("No metrics defined")).toBeInTheDocument();
    expect(screen.queryByText("Success criteria")).not.toBeInTheDocument();
    expect(screen.queryByText("Target date")).not.toBeInTheDocument();
  });

  it("SIG-5e: 'View origin activity' hidden when the origin IS the current activity", () => {
    render(
      <SignalDetailPanel signal={OBJ_WITH_ORIGIN} signalType="objective" currentActivityId="act-9" />,
    );
    expect(screen.queryByRole("button", { name: /view origin activity/i })).not.toBeInTheDocument();
  });

  it("SIG-5e: 'View origin activity' shown when the origin differs (DC/Account)", () => {
    render(
      <SignalDetailPanel signal={OBJ_WITH_ORIGIN} signalType="objective" currentActivityId="act-OTHER" />,
    );
    expect(screen.getByRole("button", { name: /view origin activity/i })).toBeInTheDocument();
  });

  it("SIG-5e-fix: summary reads as a paragraph; no Domain/Dimension rows (recap only)", () => {
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    // Summary is a plain paragraph — no "Summary" column label.
    expect(screen.getByText("Reduce reporting time by 50%")).toBeInTheDocument();
    expect(screen.queryByText("Summary")).not.toBeInTheDocument();
    // Domain / Dimension separate rows are gone — the recap conveys them.
    expect(screen.queryByText("Domain")).not.toBeInTheDocument();
    expect(screen.queryByText("Dimension")).not.toBeInTheDocument();
    expect(screen.getByText("Operations × Time")).toBeInTheDocument();
  });

  it("SIG-5e: keeps the bottom actions (Edit; Validate/Reject on a pending objective)", () => {
    render(
      <SignalDetailPanel
        signal={{ ...MOCK_OBJECTIVE, status: "PENDING" }}
        signalType="objective"
        onValidate={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /validate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
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
    // SIG-5f: the ORIGIN contact name is bold/primary (the per-type Contact row
    // also shows the name, so pick the emphasised ContactInline span), with the
    // job · department in muted (separate spans).
    const boldName = screen
      .getAllByText("Dana Lee")
      .find((n) => getComputedStyle(n).fontWeight === "600");
    expect(boldName).toBeTruthy();
    expect(getComputedStyle(boldName).color).toBe(testTheme.palette.text.primary);
    const meta = screen.getByText(/CMO · Marketing/);
    expect(getComputedStyle(meta).color).toBe(testTheme.palette.text.secondary);
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

// ==============================|| SIG-4 — MULTI-DEPARTMENT SCOPE (M2M) ||============================== //
//
// Pain / Impact / Constraint carry `target_departments` (M2M, a list of
// {id,name}). The detail drawer must show ALL of them, joined "A, B, C" — not a
// single name read off the removed singular `target_department` FK. Objective /
// People keep the single FK and are unchanged.

describe("SignalDetailPanel — multi-department scope (SIG-4)", () => {
  const CONSTRAINT_MULTI = {
    id: "cn-multi",
    status: "PENDING",
    summary: "Must comply with SOC2 across teams",
    nature_display: "Regulatory",
    rigidity_display: "Firm",
    target_departments: [
      { id: "d1", name: "Sales" },
      { id: "d2", name: "Marketing" },
      { id: "d3", name: "Finance" },
    ],
    source_quote: "We must comply",
    contact: null,
    source_context: { contacts: [] },
  };

  it("Constraint: shows ALL target_departments joined 'A, B, C'", () => {
    render(<SignalDetailPanel signal={CONSTRAINT_MULTI} signalType="constraints" />);
    expect(screen.getByText("Sales, Marketing, Finance")).toBeInTheDocument();
  });

  it("Constraint: a single department shows just its name", () => {
    const one = { ...CONSTRAINT_MULTI, id: "cn-one", target_departments: [{ id: "d1", name: "Sales" }] };
    render(<SignalDetailPanel signal={one} signalType="constraints" />);
    expect(screen.getByText("Sales")).toBeInTheDocument();
  });

  it("Constraint: an empty department list hides the row (no stray name, no crash)", () => {
    const none = { ...CONSTRAINT_MULTI, id: "cn-none", target_departments: [] };
    render(<SignalDetailPanel signal={none} signalType="constraints" />);
    // The section still renders (rigidity present) but no department text leaks.
    expect(screen.getByText("Firm")).toBeInTheDocument();
    expect(screen.queryByText("Sales")).not.toBeInTheDocument();
  });

  it("Pain: shows ALL target_departments joined", () => {
    const painMulti = {
      ...MOCK_PAIN,
      id: "pn-multi",
      target_departments: [
        { id: "d1", name: "Sales" },
        { id: "d2", name: "Operations" },
      ],
    };
    render(<SignalDetailPanel signal={painMulti} signalType="pain" />);
    expect(screen.getByText("Sales, Operations")).toBeInTheDocument();
  });

  it("Impact: shows ALL target_departments joined", () => {
    const impactMulti = {
      ...MOCK_IMPACT,
      id: "im-multi",
      target_departments: [
        { id: "d2", name: "Marketing" },
        { id: "d3", name: "Finance" },
      ],
    };
    render(<SignalDetailPanel signal={impactMulti} signalType="impact" />);
    expect(screen.getByText("Marketing, Finance")).toBeInTheDocument();
  });

  it("Objective (mono FK): its single target_department is UNCHANGED (not joined)", () => {
    // MOCK_OBJECTIVE carries the singular target_department FK ({name:'Finance'})
    // rendered in the Scope label/value row. SIG-4 must not touch it.
    render(<SignalDetailPanel signal={MOCK_OBJECTIVE} signalType="objective" />);
    expect(screen.getByText("Finance")).toBeInTheDocument();
  });
});

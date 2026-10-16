// frontend/src/__tests__/components/signals/TechStackDetailView.test.jsx
//
// Sprint TechStack T1 — the TechStack detail on the standard drawer chassis
// (Activity surface only), skeleton of PeopleDetailView. 5 sections in this
// order: Technology → Usage → Lifecycle → Notes → Source (Source LAST).
//   - Usage in three cases: DEPARTMENT → the departments; COMPANY / UNKNOWN →
//     the choices label; null → "Unknown" (never a "—" placeholder).
//   - Lifecycle: empty start year / renewal / cost → "Unknown"; the
//     discontinuation line ONLY when is_discontinued ("Discontinued on <date>").
//   - Removed: "Mentioned by" and "To replace".
// DC / Account (no currentActivityId, or the cluster coque's leading/trailing
// actions) keep the flush branch (TechDetailBlock) unchanged.

import { describe, it, expect, afterEach } from "vitest";
import { render as rtlRender, screen, cleanup, within } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import SignalDetailContent from "components/signals/SignalDetailContent";

const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

afterEach(() => cleanup());

// The real /signals/choices/ shape for usage_scopes (backend UsageScope, T0).
const CHOICES = {
  usage_scopes: [
    { value: "DEPARTMENT", label: "Department" },
    { value: "COMPANY", label: "Company" },
    { value: "UNKNOWN", label: "Unknown" },
  ],
};

const TECH = {
  id: "ts-chassis",
  status: "PENDING",
  tech_name: "HubSpot",
  is_to_replace: true,
  usage_scope: "DEPARTMENT",
  usage_scope_display: "Department",
  usage_departments: [
    { id: "3", name: "Marketing" },
    { id: "5", name: "Sales" },
  ],
  usage_start_year: 2021,
  renewal_date: "2026-06-15",
  cost_description: "~50k/year",
  is_discontinued: false,
  discontinued_date: null,
  notes: "They find the reporting clunky.",
  source_quote: "Marketing and Sales both live in HubSpot.",
  source_context: {
    activity: { id: "act-origin" },
    contacts: [{ id: "c2", first_name: "Jane", last_name: "Doe" }],
  },
};

const renderChassis = (signal, extra = {}) =>
  render(
    <SignalDetailPanel
      signal={signal}
      signalType="tech-stack"
      currentActivityId="act-1"
      choices={CHOICES}
      {...extra}
    />,
  );

describe("TechStack detail on the chassis (Activity, T1)", () => {
  it("T1-1: tech-stack + currentActivityId → chassis body, 5 sections in order, Source last", () => {
    renderChassis(TECH);
    const body = screen.getByTestId("techstack-detail-body");
    const titles = ["Technology", "Usage", "Lifecycle", "Notes", "Source"].map((t) =>
      within(body).getByText(t),
    );
    for (let i = 1; i < titles.length; i += 1) {
      // Each section header comes AFTER the previous one in the document.
      expect(
        titles[i - 1].compareDocumentPosition(titles[i]) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    }
    // Flush markers absent.
    expect(screen.queryByText("TOOL USAGE")).not.toBeInTheDocument();
    expect(screen.queryByText("IDENTITY")).not.toBeInTheDocument();
  });

  it("T1-2: §1 Technology shows the tool name only", () => {
    renderChassis(TECH);
    expect(screen.getByTestId("techstack-summary-text")).toHaveTextContent("HubSpot");
  });

  it("T1-3: no 'Mentioned by' and no 'To replace' (even when is_to_replace is true)", () => {
    renderChassis(TECH);
    expect(screen.queryByText(/Mentioned by/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/To replace/i)).not.toBeInTheDocument();
  });

  it("T1-4: usage DEPARTMENT → the departments", () => {
    renderChassis(TECH);
    const usage = screen.getByTestId("techstack-usage");
    expect(usage).toHaveTextContent("Marketing, Sales");
  });

  it("T1-5: usage COMPANY → 'Company' (choices label)", () => {
    renderChassis({
      ...TECH, id: "ts-company", usage_scope: "COMPANY", usage_scope_display: "Company",
      usage_departments: [],
    });
    expect(screen.getByTestId("techstack-usage")).toHaveTextContent("Company");
  });

  it("T1-6: usage UNKNOWN → 'Unknown' in full", () => {
    renderChassis({
      ...TECH, id: "ts-unknown", usage_scope: "UNKNOWN", usage_scope_display: "Unknown",
      usage_departments: [],
    });
    expect(screen.getByTestId("techstack-usage")).toHaveTextContent("Unknown");
  });

  it("T1-7: usage null → 'Unknown' in full (never a '—' placeholder)", () => {
    renderChassis({
      ...TECH, id: "ts-null", usage_scope: null, usage_scope_display: null,
      usage_departments: [],
    });
    const usage = screen.getByTestId("techstack-usage");
    expect(usage).toHaveTextContent("Unknown");
    expect(usage).not.toHaveTextContent("—");
  });

  it("T1-8: lifecycle values shown when present", () => {
    renderChassis(TECH);
    const lifecycle = screen.getByTestId("techstack-lifecycle");
    expect(lifecycle).toHaveTextContent("2021");
    expect(lifecycle).toHaveTextContent("15 Jun 2026");
    expect(lifecycle).toHaveTextContent("~50k/year");
  });

  it("T1-9: empty start year / renewal / cost → 'Unknown' on each row", () => {
    renderChassis({
      ...TECH, id: "ts-empty-lifecycle",
      usage_start_year: null, renewal_date: null, cost_description: "",
    });
    const lifecycle = screen.getByTestId("techstack-lifecycle");
    expect(within(lifecycle).getAllByText("Unknown")).toHaveLength(3);
  });

  it("T1-10: discontinuation line ONLY when is_discontinued", () => {
    renderChassis(TECH);
    expect(screen.getByTestId("techstack-lifecycle")).not.toHaveTextContent(/Discontinued/i);
    cleanup();

    renderChassis({
      ...TECH, id: "ts-disc", is_discontinued: true, discontinued_date: "2026-06-30",
    });
    expect(screen.getByTestId("techstack-lifecycle")).toHaveTextContent(
      "Discontinued on 30 Jun 2026",
    );
  });

  it("T1-11: notes shown; empty notes → the neutral 'No notes' placeholder (not 'Unknown')", () => {
    renderChassis(TECH);
    expect(screen.getByTestId("techstack-notes")).toHaveTextContent("They find the reporting clunky.");
    cleanup();

    renderChassis({ ...TECH, id: "ts-no-notes", notes: "" });
    const notes = screen.getByTestId("techstack-notes");
    expect(notes).toHaveTextContent("No notes");
    expect(notes).not.toHaveTextContent("Unknown");
  });

  it("T1-12: §5 Source — quote, participants and origin link", () => {
    renderChassis(TECH);
    const source = screen.getByTestId("techstack-source");
    expect(source).toHaveTextContent("Marketing and Sales both live in HubSpot.");
    expect(within(source).getByText("Jane Doe")).toBeInTheDocument();
    expect(within(source).getByRole("button", { name: /view origin activity/i })).toBeInTheDocument();
  });

  it("T1-13 (witness): tech-stack WITHOUT currentActivityId (DC/Account) → flush branch unchanged", () => {
    render(<SignalDetailPanel signal={TECH} signalType="tech-stack" />);
    expect(screen.queryByTestId("techstack-detail-body")).not.toBeInTheDocument();
    expect(screen.getByText("IDENTITY")).toBeInTheDocument();
    expect(screen.getByText("TOOL USAGE")).toBeInTheDocument();
    expect(screen.getByText("Mentioned by")).toBeInTheDocument();
    expect(screen.getByText("To replace")).toBeInTheDocument();
  });

  it("T1-14 (witness): tech-stack + leading/trailing (cluster coque) → flush branch", () => {
    render(
      <SignalDetailContent
        signal={TECH}
        signalType="tech-stack"
        currentActivityId="act-1"
        leadingAction={<span>back</span>}
        trailingAction={<span>close</span>}
      />,
    );
    expect(screen.queryByTestId("techstack-detail-body")).not.toBeInTheDocument();
    expect(screen.getByText("TOOL USAGE")).toBeInTheDocument();
  });
});

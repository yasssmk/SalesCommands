// frontend/src/__tests__/components/signals/SignalDetailStructure.test.jsx
//
// Lot 3 / 8 (TD-276, PO decision) — the DETAIL follows the structure of the
// EDIT drawer (design 5.18) for Pain, Constraint and People: same blocks, same
// order (the detail keeps its short noun titles — question titles on the edit
// side are accepted, rule C2b). Edit structures:
//   Pain       — §1 What's the pain? · §2 Which scope? · §3 Related tool (+ notes) · §4 Source quote
//   Constraint — §1 What's the constraint? · §2 Rigidity · §3 Which scope? · §4 Notes · §5 Source quote
//   People     — §1 Who is this person? (contact, name, department) · §2 What is their role? · §3 Source quote
// sectionHeaders: the shared helper of the C2b parity test (_utils/sectionHeaders).

import { describe, it, expect, afterEach } from "vitest";
import { render as rtlRender, screen, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import { sectionOf, sectionTitles } from "../../_utils/sectionHeaders";

const render = (ui) => rtlRender(ui, { wrapper: AphoriqTheme });
afterEach(() => cleanup());

const titles = sectionTitles;

describe("Pain detail — the edit's structure", () => {
  const PAIN = {
    id: "p1", status: "PENDING", summary: "Lost 5h/week on consolidation",
    what: "DATA", dimension: "TIME", what_display: "Data", dimension_display: "Time",
    scope_level: "DEPARTMENT", scope_level_display: "Department",
    target_departments: [{ id: "d1", name: "Sales" }],
    signal_category_display: "Operational",
    related_techstack_mention: "Excel", notes: "Critical for Q3",
    source_quote: "We lose 5 hours a week", source_context: { contacts: [] },
  };

  it("§1 Diagnosis · §2 Scope · §3 Related tool · §4 Source", () => {
    const { container } = render(<SignalDetailPanel signal={PAIN} signalType="pain" />);
    expect(titles(container)).toEqual(["Diagnosis", "Scope", "Related tool", "Source"]);
  });

  it("the related tool and the notes are in §3, the category stays in §2", () => {
    const { container } = render(<SignalDetailPanel signal={PAIN} signalType="pain" />);
    expect(sectionOf(container, screen.getByText("Excel"))).toBe(3);
    expect(sectionOf(container, screen.getByText("Critical for Q3"))).toBe(3);
    expect(sectionOf(container, screen.getByText("Operational"))).toBe(2);
  });
});

describe("Constraint detail — the edit's structure", () => {
  const CONSTRAINT = {
    id: "c1", status: "PENDING", summary: "Must comply with SOC 2 everywhere",
    nature: "SECURITY", nature_display: "Security", rigidity: "FIRM", rigidity_display: "Firm",
    notes: "Auditors arrive in Q3.", target_departments: [{ id: "d1", name: "IT" }],
    source_quote: "We can't move forward without SOC 2.", source_context: { contacts: [] },
  };

  it("§1 Summary · §2 Rigidity · §3 Scope · §4 Notes · §5 Source", () => {
    const { container } = render(<SignalDetailPanel signal={CONSTRAINT} signalType="constraints" />);
    expect(titles(container)).toEqual(["Summary", "Rigidity", "Scope", "Notes", "Source"]);
  });

  it("the rigidity is shown once, in §2", () => {
    const { container } = render(<SignalDetailPanel signal={CONSTRAINT} signalType="constraints" />);
    const firm = screen.getByText("Firm");
    expect(sectionOf(container, firm)).toBe(2);
  });

  it("no rigidity → the edit's placeholder in §2", () => {
    const { container } = render(
      <SignalDetailPanel signal={{ ...CONSTRAINT, rigidity: "", rigidity_display: "" }} signalType="constraints" />,
    );
    expect(sectionOf(container, screen.getByText("No rigidity"))).toBe(2);
  });
});

describe("People detail — the edit's structure", () => {
  const PEOPLE = {
    id: "pp1", status: "PENDING", role: "ECONOMIC_BUYER", role_display: "Economic Buyer",
    influence: "HIGH", influence_display: "High", full_name: "Marc Dubois",
    target_contact: null, target_department: { id: "d1", name: "Finance" },
    notes: "Signs off every budget line.", source_quote: "Marc will have the final word.",
    source_context: { contacts: [] },
  };

  it("§1 Person · §2 Role · §3 Source", () => {
    const { container } = render(
      <SignalDetailPanel signal={PEOPLE} signalType="people" currentActivityId="act-1" />,
    );
    expect(titles(container)).toEqual(["Person", "Role", "Source"]);
  });

  it("the contact and the department are in §1 (Who is this person?)", () => {
    const { container } = render(
      <SignalDetailPanel signal={PEOPLE} signalType="people" currentActivityId="act-1" />,
    );
    expect(sectionOf(container, screen.getByTestId("people-contact"))).toBe(1);
    expect(sectionOf(container, screen.getByText("No contact attributed"))).toBe(1);
  });
});

// ==============================|| 8i-1 — EVERY DETAIL, THE EDIT'S STRUCTURE + PLACEHOLDERS ||============================== //
// Extension of TD-276 (PO): the detail follows the edit — same sections, same
// order — and an empty field reads the edit's placeholder, never vanishes.

describe("The other details — the edit's sections (8i-1)", () => {
  const base = { id: "x1", status: "PENDING", source_quote: "", source_context: { contacts: [] } };
  it.each([
    ["objective", { summary: "Cut reporting time", scope_level: "BUSINESS" }, ["Goal", "Scope", "Metrics", "Source"]],
    ["impact", { summary: "Lose 2 days a month", scope_level: "BUSINESS" }, ["Diagnosis", "Scope", "Metrics", "Source"]],
    ["blockers", { summary: "No budget" }, ["Summary", "Raised by", "Source"]],
    ["tech-stack", { tech_name: "Salesforce" }, ["Technology", "Usage", "Lifecycle", "Notes", "Source"]],
    ["competitors", { competitor_name: "Acme CRM", summary: "" }, ["Competitor", "Source"]],
  ])("%s: the edit drawer's sections, in its order", (signalType, fields, expected) => {
    const { container } = render(
      <SignalDetailPanel signal={{ ...base, ...fields }} signalType={signalType} currentActivityId="act-1" />,
    );
    expect(titles(container)).toEqual(expected);
  });
});

describe("Objective detail — §3 placeholders, as the edit (8i-1)", () => {
  const OBJ = { id: "o1", status: "PENDING", summary: "Cut reporting time", scope_level: "BUSINESS",
    success_criteria: "", target_date: null, notes: "", source_quote: "", source_context: { contacts: [] } };

  it("only a target date: the date + « No success criteria » + « No notes », all in §3", () => {
    const { container } = render(
      <SignalDetailPanel signal={{ ...OBJ, target_date: "2026-12-31" }} signalType="objective" />,
    );
    expect(sectionOf(container, screen.getByText("No success criteria"))).toBe(3);
    expect(sectionOf(container, screen.getByText("No notes"))).toBe(3);
    expect(screen.getByText("Target date")).toBeInTheDocument();
  });

  it("all empty: the three placeholders (no single « No metrics defined » line)", () => {
    const { container } = render(<SignalDetailPanel signal={OBJ} signalType="objective" />);
    ["No success criteria", "No date set", "No notes"].forEach((t) =>
      expect(sectionOf(container, screen.getByText(t))).toBe(3));
    expect(screen.queryByText("No metrics defined")).toBeNull();
  });
});

describe("Impact detail — §3 placeholders, as the edit (8i-1)", () => {
  const IMP = { id: "i1", status: "PENDING", summary: "Lose 2 days a month", scope_level: "BUSINESS",
    impact_type: "", impact_type_display: "", metric_text: "", source_quote: "", source_context: { contacts: [] } };

  it("a description without type: the description stays + « No impact type »", () => {
    const { container } = render(
      <SignalDetailPanel signal={{ ...IMP, metric_text: "Two days lost every month" }} signalType="impact" />,
    );
    expect(sectionOf(container, screen.getByText("Two days lost every month"))).toBe(3);
    expect(sectionOf(container, screen.getByText("No impact type"))).toBe(3);
  });

  it("both empty: « No impact type » + « No metric defined »", () => {
    const { container } = render(<SignalDetailPanel signal={IMP} signalType="impact" />);
    expect(sectionOf(container, screen.getByText("No impact type"))).toBe(3);
    expect(sectionOf(container, screen.getByText("No metric defined"))).toBe(3);
  });
});

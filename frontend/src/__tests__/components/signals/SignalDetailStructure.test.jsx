// frontend/src/__tests__/components/signals/SignalDetailStructure.test.jsx
//
// Lot 3 / 8 (TD-276, PO decision) — the DETAIL follows the structure of the
// EDIT drawer (design 5.18) for Pain, Constraint and People: same blocks, same
// order (the detail keeps its short noun titles — question titles on the edit
// side are accepted, rule C2b). Edit structures:
//   Pain       — §1 What's the pain? · §2 Which scope? · §3 Related tool (+ notes) · §4 Source quote
//   Constraint — §1 What's the constraint? · §2 Rigidity · §3 Which scope? · §4 Notes · §5 Source quote
//   People     — §1 Who is this person? (contact, name, department) · §2 What is their role? · §3 Source quote
// sectionHeaders: same helper as EditCompetitorContent.test.jsx (C2b).

import { describe, it, expect, afterEach } from "vitest";
import { render as rtlRender, screen, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";
import SignalDetailPanel from "components/signals/SignalDetailPanel";

const render = (ui) => rtlRender(ui, { wrapper: AphoriqTheme });
afterEach(() => cleanup());

function sectionHeaders(root) {
  return [...root.querySelectorAll(".MuiChip-label")]
    .filter((label) => /^\d+$/.test(label.textContent))
    .map((label) => {
      const row = label.closest(".MuiChip-root").parentElement;
      return { index: label.textContent, title: row.textContent.slice(label.textContent.length), el: row };
    });
}

// `el` sits in section n (1-based): after its header, before the next one.
function sectionOf(container, el) {
  const headers = sectionHeaders(container).map((h) => h.el);
  const after = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
  let n = 0;
  headers.forEach((h, i) => { if (after(h, el)) n = i + 1; });
  return n;
}

const titles = (container) => sectionHeaders(container).map(({ title }) => title);

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

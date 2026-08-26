// frontend/src/__tests__/signals/SignalsGroupedView.layout.test.jsx
//
// C3: Activity Qualification groups by TYPE with flat signal lists — no
// clusters, no domain×dimension accordion. Rows are informational; clicking
// one opens the drawer.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalsGroupedView from "sections/activities/signals/SignalsGroupedView";

afterEach(() => {
  cleanup();
});

const makeQual = (id, type, what = "OPS", dimension = "TIME") => ({
  id,
  _signalType: type,
  status: "PENDING",
  summary: `${type} ${id}`,
  what,
  what_display: what,
  dimension,
  dimension_display: dimension,
  source_context: { contacts: [] },
});

const makeBlocker = (id) => ({
  id,
  _signalType: "blockers",
  status: "PENDING",
  summary: `Blocker ${id}`,
  source_context: { contacts: [] },
});

const makeTechStack = (id, name = "Salesforce") => ({
  id,
  _signalType: "tech-stack",
  status: "PENDING",
  tech_name: name,
  source_context: { contacts: [] },
});

describe("SignalsGroupedView — type sections (Activity)", () => {
  it("renders the five type-section headers", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[
          makeQual("o1", "objective"),
          makeQual("p1", "pain"),
          makeQual("i1", "impact"),
        ]}
        techStackSignals={[makeTechStack("t1")]}
        blockerSignals={[makeBlocker("b1")]}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Objectives")).toBeInTheDocument();
    expect(screen.getByText("Pains")).toBeInTheDocument();
    expect(screen.getByText("Impacts")).toBeInTheDocument();
    // "Tech Stack" is also the type-chip label on the tech row → at least one.
    expect(screen.getAllByText("Tech Stack").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Objections")).toBeInTheDocument();
  });

  it("shows a correct count per section", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[
          makeQual("p1", "pain"),
          makeQual("p2", "pain"),
          makeQual("p3", "pain"),
          makeQual("o1", "objective"),
        ]}
        techStackSignals={[makeTechStack("t1"), makeTechStack("t2")]}
        blockerSignals={[]}
        onSelect={vi.fn()}
      />,
    );

    // Counts render as "(N)" next to the header.
    expect(screen.getByText("(3)")).toBeInTheDocument(); // Pains
    // Objectives (1) and Impacts (0) both exist; (1) appears once here.
    expect(screen.getByText("(2)")).toBeInTheDocument(); // Tech Stack
  });

  it("renders each type as a flat list of SignalLine rows (no cluster cards)", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[makeQual("p1", "pain"), makeQual("o1", "objective")]}
        techStackSignals={[makeTechStack("t1")]}
        blockerSignals={[]}
        onSelect={vi.fn()}
      />,
    );

    // Flat rows — one signal-line per signal, no cluster card wrapper.
    expect(screen.getAllByTestId("signal-line").length).toBe(3);
    // The SignalClusterCard renders a "Cluster actions" menu button — its
    // absence proves no cluster card is on the Activity view.
    expect(
      screen.queryByRole("button", { name: /cluster actions/i }),
    ).not.toBeInTheDocument();
  });

  it("does NOT render a domain×dimension accordion / theme header", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[
          makeQual("p1", "pain", "OPS", "TIME"),
          makeQual("p2", "pain", "DATA", "COST"),
        ]}
        techStackSignals={[]}
        blockerSignals={[]}
        onSelect={vi.fn()}
      />,
    );

    // The old theme grouping rendered "WHAT × DIMENSION" labels — gone now.
    expect(screen.queryByText("OPS × TIME")).not.toBeInTheDocument();
    expect(screen.queryByText("DATA × COST")).not.toBeInTheDocument();
    // Both pains still appear, flat, under the single Pains section.
    expect(screen.getAllByTestId("signal-line").length).toBe(2);
  });

  it("rows are informational (no action buttons) and open the drawer on click", () => {
    const onSelect = vi.fn();
    render(
      <SignalsGroupedView
        qualificationSignals={[makeQual("p1", "pain")]}
        techStackSignals={[]}
        blockerSignals={[]}
        onSelect={onSelect}
      />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("signal-line"));
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: "p1" }),
      "pain",
    );
  });

  it("shows a neutral empty note for an empty section (not the global empty)", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[makeQual("p1", "pain")]}
        techStackSignals={[]}
        blockerSignals={[]}
        onSelect={vi.fn()}
      />,
    );

    // Objectives/Impacts/Tech/Objections are empty → neutral notes, not red,
    // and NOT the global "no signals" state (there is a pain).
    expect(screen.getByText("No objectives extracted yet")).toBeInTheDocument();
    expect(screen.getByText("No tools detected")).toBeInTheDocument();
    expect(
      screen.queryByText("No signals found for this activity"),
    ).not.toBeInTheDocument();
  });

  it("shows the global empty state when every section is empty", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[]}
        techStackSignals={[]}
        blockerSignals={[]}
        onSelect={vi.fn()}
      />,
    );
    expect(
      screen.getByText("No signals found for this activity"),
    ).toBeInTheDocument();
  });

  it("renders the two-column reference layout: narrative LEFT, Tech/Objections RIGHT (flat)", () => {
    const { container } = render(
      <SignalsGroupedView
        qualificationSignals={[makeQual("p1", "pain"), makeQual("o1", "objective")]}
        techStackSignals={[makeTechStack("t1")]}
        blockerSignals={[makeBlocker("b1")]}
        onSelect={vi.fn()}
      />,
    );
    const cols = container.querySelectorAll(".MuiGrid-container > .MuiGrid-item");
    expect(cols).toHaveLength(2);
    const [left, right] = cols;
    expect(left).toHaveTextContent("Objectives");
    expect(left).toHaveTextContent("Pains");
    expect(left).toHaveTextContent("Impacts");
    expect(right).toHaveTextContent("Tech Stack");
    expect(right).toHaveTextContent("Objections");
    // Activity is flat — no domain×dimension header inside the left sections.
    expect(left).not.toHaveTextContent("OPS × TIME");
  });

  it("type sections are collapsible and open by default", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[makeQual("p1", "pain")]}
        techStackSignals={[]}
        blockerSignals={[]}
        onSelect={vi.fn()}
      />,
    );
    const header = screen.getByRole("button", { name: /Pains/i });
    expect(header).toHaveAttribute("aria-expanded", "true"); // open by default
    fireEvent.click(header);
    expect(header).toHaveAttribute("aria-expanded", "false"); // collapses
    fireEvent.click(header);
    expect(header).toHaveAttribute("aria-expanded", "true");
  });

  it("keeps tech-stack out of the qualification sections", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[makeQual("p1", "pain")]}
        techStackSignals={[makeTechStack("t1", "Salesforce")]}
        blockerSignals={[]}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.getByText("pain p1")).toBeInTheDocument();
  });
});

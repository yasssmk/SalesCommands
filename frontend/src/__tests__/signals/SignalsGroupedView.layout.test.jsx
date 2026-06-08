// frontend/src/__tests__/signals/SignalsGroupedView.layout.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import SignalsGroupedView from "sections/activities/signals/SignalsGroupedView";

afterEach(() => {
  cleanup();
});

const makePain = (id, what = "OPS", dimension = "TIME") => ({
  id,
  _signalType: "pain",
  status: "PENDING",
  summary: `Pain ${id}`,
  what,
  what_display: what,
  dimension,
  dimension_display: dimension,
});

const makeBlocker = (id) => ({
  id,
  _signalType: "blockers",
  status: "PENDING",
  summary: `Blocker ${id}`,
  contact: null,
  source_context: { contacts: [] },
});

const makeTechStack = (id, name = "Tool") => ({
  id,
  _signalType: "tech-stack",
  status: "PENDING",
  summary: name,
  tech_catalog_entry: null,
  metadata: { pending_tech_name: name },
});

describe("SignalsGroupedView — 3-zone layout", () => {
  it("renders Qualification, Blockers, and Tech Stack section headers", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[makePain("p1")]}
        techStackSignals={[makeTechStack("t1", "Salesforce")]}
        blockerSignals={[makeBlocker("b1")]}
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("Qualification")).toBeInTheDocument();
    expect(screen.getByText("Blockers / Objections")).toBeInTheDocument();
    expect(screen.getAllByText("Tech Stack").length).toBeGreaterThanOrEqual(1);
  });

  it("shows TechStack signals in Tech Stack section, not in Qualification", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[makePain("p1")]}
        techStackSignals={[makeTechStack("t1", "Salesforce")]}
        blockerSignals={[]}
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.getByText("Pain p1")).toBeInTheDocument();
  });

  it("shows empty state for Qualification when no qualification signals", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[]}
        techStackSignals={[makeTechStack("t1", "Jira")]}
        blockerSignals={[]}
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("No qualification signals extracted yet")).toBeInTheDocument();
  });

  it("shows empty state for Blockers when no blockers", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[makePain("p1")]}
        techStackSignals={[]}
        blockerSignals={[]}
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("No blockers identified")).toBeInTheDocument();
  });

  it("shows empty state for Tech Stack when no tech-stack signals", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[makePain("p1")]}
        techStackSignals={[]}
        blockerSignals={[makeBlocker("b1")]}
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("No tools detected")).toBeInTheDocument();
  });

  it("shows global empty state when all zones are empty", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[]}
        techStackSignals={[]}
        blockerSignals={[]}
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("No signals found for this activity")).toBeInTheDocument();
  });

  it("groups qualification signals by theme", () => {
    render(
      <SignalsGroupedView
        qualificationSignals={[
          makePain("p1", "OPS", "TIME"),
          makePain("p2", "OPS", "TIME"),
          makePain("p3", "DATA", "COST"),
        ]}
        techStackSignals={[]}
        blockerSignals={[]}
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("OPS × TIME")).toBeInTheDocument();
    expect(screen.getByText("DATA × COST")).toBeInTheDocument();
  });
});

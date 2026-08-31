// frontend/src/__tests__/signals/cardBlockAdoption.test.jsx
//
// B1.2.1: the rich Account cards consume the shared per-type detail blocks
// for their type-specific section. These tests assert each card still renders
// its type's fields (now via the shared block) AND its actions still fire.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

import ImpactCard from "components/cards/signals/ImpactCard";
import ObjectiveCard from "components/cards/signals/ObjectiveCard";
import TechStackCard from "components/cards/signals/TechStackCard";
import PainCard from "components/cards/signals/PainCard";

afterEach(() => cleanup());

describe("ImpactCard adopts ImpactDetailBlock", () => {
  const impact = {
    id: "i1",
    status: "PENDING",
    what: "OPS",
    dimension: "TIME",
    impact_type: "TIME",
    impact_type_display: "Time impact",
    metric_text: "5 hours per week",
    human_impact: "FRUSTRATION",
    human_impact_display: "Frustration",
    scope_level: "BUSINESS",
    summary: "Lost time on manual consolidation",
    created_at: "2026-05-01T10:00:00Z",
  };

  it("renders impact_type, metric and human_impact via the shared block", () => {
    render(<ImpactCard impact={impact} choices={{}} onValidate={vi.fn()} onReject={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("IMPACT EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText("Time impact")).toBeInTheDocument();
    expect(screen.getByText("5 hours per week")).toBeInTheDocument();
    expect(screen.getByText("Frustration")).toBeInTheDocument();
  });

  it("still fires onValidate when the validate action is clicked", () => {
    const onValidate = vi.fn();
    render(<ImpactCard impact={impact} choices={{}} onValidate={onValidate} onReject={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /validate impact/i }));
    expect(onValidate).toHaveBeenCalledWith(impact, "impact");
  });
});

describe("ObjectiveCard adopts ObjectiveDetailBlock", () => {
  const objective = {
    id: "o1",
    status: "PENDING",
    what: "OPS",
    dimension: "TIME",
    scope_level: "DEPARTMENT",
    target_department: { id: "d1", name: "Finance" },
    success_criteria: "Reports in 2 hours",
    target_date: "2020-01-01",
    summary: "Cut reporting time",
    created_at: "2026-05-01T10:00:00Z",
  };

  it("renders target date/urgency, success criteria and owner via the block", () => {
    render(<ObjectiveCard objective={objective} choices={{}} onValidate={vi.fn()} onReject={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("OBJECTIVE")).toBeInTheDocument();
    expect(screen.getByText("Reports in 2 hours")).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
    expect(screen.getByText("Department: Finance")).toBeInTheDocument();
  });

  it("still fires onValidate when the validate action is clicked", () => {
    const onValidate = vi.fn();
    render(<ObjectiveCard objective={objective} choices={{}} onValidate={onValidate} onReject={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /validate objective/i }));
    expect(onValidate).toHaveBeenCalledWith(objective, "objective");
  });
});

describe("TechStackCard adopts TechDetailBlock", () => {
  const tech = {
    id: "t1",
    status: "PENDING",
    tech_name: "Salesforce",
    is_competitor: true,
    is_integration: false,
    is_to_replace: true,
    usage_scope_display: "Company-wide",
    usage_start_year: 2022,
    cost_description: "~50k/year",
    created_at: "2026-05-01T10:00:00Z",
  };

  it("renders qualification flags, usage and lifecycle via the block", () => {
    render(<TechStackCard techStack={tech} onValidate={vi.fn()} onReject={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    // Competitor is its own signal type now — the retired manual tag never
    // renders a chip, even with a legacy is_competitor=true on the payload.
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    expect(screen.getByText("To replace")).toBeInTheDocument();
    expect(screen.getByText("Company-wide")).toBeInTheDocument();
    expect(screen.getByText("2022")).toBeInTheDocument();
    expect(screen.getByText("~50k/year")).toBeInTheDocument();
  });

  it("still fires onValidate when the validate action is clicked", () => {
    const onValidate = vi.fn();
    render(<TechStackCard techStack={tech} onValidate={onValidate} onReject={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /validate signal/i }));
    expect(onValidate).toHaveBeenCalledWith(tech, "tech-stack");
  });
});

describe("PainCard adopts PainDetailBlock", () => {
  const pain = {
    id: "p1",
    status: "PENDING",
    what: "TECH",
    dimension: "QUALITY",
    related_techstack_mention: "Excel",
    summary: "Spreadsheet chaos",
    created_at: "2026-05-01T10:00:00Z",
  };

  it("renders related_techstack_mention via the block", () => {
    render(<PainCard pain={pain} choices={{}} onValidate={vi.fn()} onReject={vi.fn()} onEdit={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("RELATED TOOL")).toBeInTheDocument();
    expect(screen.getByText("Excel")).toBeInTheDocument();
  });
});

// frontend/src/__tests__/signals/detailBlocks.test.jsx
//
// B1.2.1: the shared per-type detail blocks are the single rendering of
// each signal type's type-specific fields, consumed by both the drawer and
// the rich cards. Each block reads *_display + raw fields off the signal.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import ImpactDetailBlock from "components/signals/detail/ImpactDetailBlock";
import ObjectiveDetailBlock from "components/signals/detail/ObjectiveDetailBlock";
import TechDetailBlock from "components/signals/detail/TechDetailBlock";
import PainDetailBlock from "components/signals/detail/PainDetailBlock";

afterEach(() => cleanup());

describe("ImpactDetailBlock", () => {
  it("renders impact_type, metric_text and human_impact", () => {
    render(
      <ImpactDetailBlock
        signal={{
          impact_type_display: "Time impact",
          metric_text: "5 hours per week",
          human_impact_display: "Frustration",
        }}
      />,
    );
    expect(screen.getByText("Time impact")).toBeInTheDocument();
    expect(screen.getByText("5 hours per week")).toBeInTheDocument();
    expect(screen.getByText("Frustration")).toBeInTheDocument();
  });

  it("renders nothing when the impact carries no type-specific fields", () => {
    const { container } = render(<ImpactDetailBlock signal={{}} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("ObjectiveDetailBlock", () => {
  it("renders success criteria and an overdue urgency chip for a past date", () => {
    render(
      <ObjectiveDetailBlock
        signal={{
          target_date: "2020-01-01",
          success_criteria: "Monthly reports in 2 hours",
          scope_level: "DEPARTMENT",
          target_department: { name: "Finance" },
        }}
      />,
    );
    expect(screen.getByText("Monthly reports in 2 hours")).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
    expect(screen.getByText("Department: Finance")).toBeInTheDocument();
  });
});

describe("TechDetailBlock", () => {
  it("renders qualification flags and lifecycle fields", () => {
    render(
      <TechDetailBlock
        signal={{
          is_competitor: true,
          is_integration: false,
          is_to_replace: true,
          usage_scope_display: "Company-wide",
          usage_start_year: 2022,
          cost_description: "~50k/year",
        }}
      />,
    );
    expect(screen.getByText("Competitor")).toBeInTheDocument();
    expect(screen.getByText("To replace")).toBeInTheDocument();
    expect(screen.queryByText("Integration")).not.toBeInTheDocument();
    expect(screen.getByText("Company-wide")).toBeInTheDocument();
    expect(screen.getByText("2022")).toBeInTheDocument();
    expect(screen.getByText("~50k/year")).toBeInTheDocument();
  });
});

describe("PainDetailBlock", () => {
  it("renders the related tool mention", () => {
    render(<PainDetailBlock signal={{ related_techstack_mention: "Excel" }} />);
    expect(screen.getByText("Excel")).toBeInTheDocument();
  });

  it("renders nothing when there is no related tool mention", () => {
    const { container } = render(<PainDetailBlock signal={{}} />);
    expect(container.firstChild).toBeNull();
  });
});

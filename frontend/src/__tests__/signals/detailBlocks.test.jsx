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

  // ONE usage line (PO rule): the department PRIMES over the scale, plain
  // text, never both. Fixes the "Company-wide" + "Marketing" contradiction.
  it("shows the department (plain text) and NOT the scale when a department is present", () => {
    const { container } = render(
      <TechDetailBlock
        signal={{
          usage_scope_display: "Company-wide",
          usage_departments: [{ id: "7", name: "Marketing & Communications" }],
        }}
      />,
    );
    // Department shown as plain text (body2), no MUI chip.
    const dept = screen.getByText("Marketing & Communications");
    expect(dept).toBeInTheDocument();
    expect(dept.closest(".MuiChip-root")).toBeNull();
    // The contradictory scale line is gone.
    expect(screen.queryByText("Company-wide")).not.toBeInTheDocument();
    expect(container.querySelector(".MuiChip-root")).toBeNull();
  });

  it("lists several departments as comma-separated plain text", () => {
    render(
      <TechDetailBlock
        signal={{
          usage_scope_display: "Company-wide",
          usage_departments: [
            { id: "6", name: "Sales" },
            { id: "5", name: "Marketing" },
          ],
        }}
      />,
    );
    expect(screen.getByText("Sales, Marketing")).toBeInTheDocument();
    expect(screen.queryByText("Company-wide")).not.toBeInTheDocument();
  });

  it("falls back to the usage scope when no department is designated", () => {
    render(
      <TechDetailBlock
        signal={{
          usage_scope_display: "Company-wide",
          usage_departments: [],
        }}
      />,
    );
    expect(screen.getByText("Company-wide")).toBeInTheDocument();
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

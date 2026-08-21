// frontend/src/components/WorkspaceBreadcrumb.test.jsx
//
// Unit tests for the pure breadcrumb builders in WorkspaceBreadcrumb.
//
// S1 focus: the ACTIVITY breadcrumb's step crumb must route to the DC
// workspace TIMELINE tab of the step's parent cycle, not to the (removed)
// per-step workspace.

import { describe, it, expect } from "vitest";

import { buildActivityBreadcrumbs } from "components/WorkspaceBreadcrumb";

describe("buildActivityBreadcrumbs — step crumb routing", () => {
  const base = {
    accountId: "acc-1",
    accountName: "ACME",
    cycleId: "cyc-9",
    stepId: "step-7",
    stepName: "Qualification",
    activityTitle: "Discovery call",
  };

  it("routes the step crumb to the DC workspace timeline of the parent cycle", () => {
    const items = buildActivityBreadcrumbs(base);
    const stepCrumb = items.find((i) => i.label === "Qualification");

    expect(stepCrumb).toBeTruthy();
    // Label unchanged — still names the step.
    expect(stepCrumb.label).toBe("Qualification");
    // Href now points at the DC workspace timeline tab for the cycle.
    expect(stepCrumb.href).toBe("/accounts/acc-1/dc/cyc-9?tab=timeline");
    // And no longer at the per-step workspace.
    expect(stepCrumb.href).not.toContain("/decisionSteps/");
  });
});

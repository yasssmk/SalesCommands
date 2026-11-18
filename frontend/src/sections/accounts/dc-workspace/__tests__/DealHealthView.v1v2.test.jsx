// frontend/src/sections/accounts/dc-workspace/__tests__/DealHealthView.v1v2.test.jsx
//
// Sprint « Deal health v2 », step 5 — DealHealthView must not regress when the
// pipeline writes the v2 « manager / coach » diagnostic. The v2 KEEPS every v1
// key (global_reading, dimensions, discovery_gaps, levers, themes,
// evidence_scope — amendment A5) and adds new ones the view does not read yet.
// The same view renders a v1 AND a v2 snapshot, without crashing, with the
// same v1 content. Harness: the real ThemeCustomization, as StatusPill.test.jsx.

import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));
vi.mock("api/aiPipelines/dealHealth", () => ({
  useGetDealHealthHistory: () => ({ snapshots: [] }),
}));
vi.mock("sections/accounts/dc-workspace/DimensionDetailDrawer", () => ({
  default: () => null,
}));

import ThemeCustomization from "themes/index";
import DealHealthView from "sections/accounts/dc-workspace/DealHealthView";

// ==============================|| FIXTURES ||============================== //

const V1_DIAGNOSTIC = {
  global_reading: "The client recognizes an operational problem.",
  dimensions: [
    { key: "problem_recognized", status: "confirmed", evidence: "Quote A", missing: "" },
    { key: "felt_pain", status: "missing_evidence", evidence: "", missing: "Not explored" },
    { key: "impact_understood", status: "unclear", evidence: "Partial", missing: "Quantification" },
    { key: "desired_gain", status: "suggested", evidence: "Mentioned goal", missing: "" },
    { key: "urgency", status: "missing_evidence", evidence: "", missing: "No timeline" },
    { key: "willingness_to_act", status: "unclear", evidence: "", missing: "Budget unclear" },
    { key: "solution_trust", status: "suggested", evidence: "Positive demo", missing: "" },
  ],
  discovery_gaps: [
    {
      kind: "qualification",
      dimension: "felt_pain",
      public_text: "Pain depth not yet qualified.",
      suggested_questions: ["How does this impact your daily work?"],
    },
  ],
  levers: {
    desires: [{ summary: "Better reporting", theme: "OPS:TIME" }],
    value: [{ summary: "10h/week recoverable", theme: "OPS:TIME" }],
    cost: [{ summary: "Budget not owned by champion" }],
    constraints: [{ summary: "ROI > 20%", rigidity: "FIRM", is_metric: true }],
  },
  themes: [{ label: "Ops efficiency", summary: "Pain recognized." }],
  evidence_scope: { validated_signals_count: 5, note: "Based on captured evidence." },
};

const V2_DIAGNOSTIC = {
  ...V1_DIAGNOSTIC,
  summary: "An operational problem is recognised; budget and timeline are unknown.",
  needs_and_urgency: { status: "suggested", assessment: "Need recognised.", cost_of_inaction: "Unknown" },
  credibility: { status: "unclear", assessment: "No proof shared yet." },
  fit_and_value: {
    status: "missing_evidence", assessment: "Requirements not documented.",
    requirements: [], competitive_position: "Unknown",
  },
  buying_process: { assessment: "Unknown", steps: [], timeline: "Unknown" },
  bant: {
    budget: { status: "not_validated", reason: "No budget this year." },
    authority: { status: "unknown", reason: "Not discussed." },
    need: { status: "validated", reason: "Problem recognised." },
    timeline: { status: "unknown", reason: "Not discussed." },
  },
  strategic_conclusion: "Find out when budgets are reallocated.",
  levers_to_invest: [{ lever: "value", why: "Quantify the gain." }],
  objectives: { deal: "Unknown", next_activity: ["Qualify the budget"] },
  missing_info: [
    { level: "BUSINESS", item: "Budget owner", why_it_matters: "BANT", suggested_question: "Who owns it?" },
  ],
  estimated_step: { step: "QUALIFICATION", reason: "BANT not validated." },
  top_arguments: [],
  stakeholders: [{ ref: "Marc", conviction_state: "SKEPTICAL", communication_language: "en" }],
};

function snapshotOf(diagnostic, schemaVersion) {
  return {
    id: "snap-1",
    decision_cycle: "cycle-1",
    diagnostic,
    snapshot_date: "2026-11-18T10:00:00Z",
    schema_version: schemaVersion,
  };
}

function renderView(snapshot) {
  return render(
    <ThemeCustomization>
      <DealHealthView snapshot={snapshot} cycleId="cycle-1" />
    </ThemeCustomization>,
  );
}

// ==============================|| TESTS ||============================== //

describe.each([
  ["v1", V1_DIAGNOSTIC, 1],
  ["v2", V2_DIAGNOSTIC, 2],
])("DealHealthView — a %s snapshot", (_name, diagnostic, schemaVersion) => {
  it("renders the v1 content without crashing", () => {
    renderView(snapshotOf(diagnostic, schemaVersion));

    expect(screen.getByText("The client recognizes an operational problem.")).toBeTruthy();
    expect(screen.getByText("Deal maturity dimensions")).toBeTruthy();
    expect(screen.getByText("Better reporting")).toBeTruthy();
    expect(screen.getByText("Based on 5 validated signals")).toBeTruthy();
  });
});

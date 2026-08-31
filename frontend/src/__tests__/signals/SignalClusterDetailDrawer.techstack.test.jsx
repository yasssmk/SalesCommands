// frontend/src/__tests__/signals/SignalClusterDetailDrawer.techstack.test.jsx
//
// Sub-step 3 (Cluster Tech Stack): the shared cluster drill-down drawer renders
// a TechStack cluster — the representative tool's fields FIRST (shared
// TechDetailBlock) then the source-signal list — reusing the same cluster↔signal
// replace/back navigation as pain/objective. The tech cluster hides the priority
// badge (neutral 'LOW' floor, not a real priority); pain keeps its real badge.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signalClusters", () => ({
  useGetClusterDetail: vi.fn(),
}));

vi.mock("api/signals/signals", () => ({
  validateSignal: vi.fn(() => Promise.resolve({ success: true })),
  reopenSignal: vi.fn(() => Promise.resolve({ success: true })),
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  rejectSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: vi.fn(() => ({ choices: {}, choicesLoading: false })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import SignalClusterDetailDrawer from "sections/accounts/signals/SignalClusterDetailDrawer";
import { useGetClusterDetail } from "api/signals/signalClusters";

// ==============================|| FIXTURES ||============================== //

const TECH_CLUSTER = {
  canonical_key: "hubspot",
  signal_type: "tech_stack",
  // Canonical axes are null for tech — no "WHAT × DIMENSION" title.
  what: null,
  what_display: null,
  dimension: null,
  dimension_display: null,
  summary: "HubSpot", // the tool name is the cluster headline
  priority_bucket: "LOW", // neutral floor — must NOT surface as a badge
  priority_score: 0,
  freshness_status: "FRESH",
  status: "VALIDATED",
  signal_count: 2,
  first_observed_at: "2026-04-01T10:00:00Z",
  last_confirmed_at: "2026-05-01T10:00:00Z",
  decision_cycle_ids: [],
  is_archived: false,
};

const TECH_MEMBERS = [
  {
    id: "t1",
    status: "VALIDATED",
    tech_name: "HubSpot",
    is_competitor: true,
    is_integration: false,
    is_to_replace: false,
    usage_scope_display: "Company-wide",
    source_quote: "we run everything on HubSpot",
    source_context: { activity: { id: "act-1" }, contacts: [] },
  },
  {
    id: "t2",
    status: "PENDING",
    tech_name: "Hubspot CRM",
    is_competitor: false,
    is_integration: false,
    is_to_replace: false,
    source_quote: "the Hubspot CRM is a bit of a mess",
    source_context: { activity: { id: "act-2" }, contacts: [] },
  },
];

const PAIN_CLUSTER = {
  canonical_key: "pain:OPS:TIME",
  signal_type: "pain",
  what: "OPS",
  what_display: "Operations",
  dimension: "TIME",
  dimension_display: "Time",
  summary: "Reporting is slow",
  priority_bucket: "HIGH",
  priority_score: 85,
  freshness_status: "FRESH",
  status: "VALIDATED",
  last_confirmed_at: "2026-05-01T10:00:00Z",
  human_impacts: [],
  metrics: [],
  decision_cycle_ids: [],
  is_archived: false,
};

function mockDetail(cluster, members) {
  useGetClusterDetail.mockReturnValue({
    cluster: { ...cluster, members },
    clusterLoading: false,
    clusterError: null,
    mutateCluster: vi.fn(),
  });
}

function renderDrawer(clusterSummary) {
  return render(
    <SignalClusterDetailDrawer
      open
      onClose={vi.fn()}
      clusterSummary={clusterSummary}
      accountId="acc-1"
      choices={{}}
      choicesLoading={false}
      onClusterChange={vi.fn()}
    />,
  );
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

// ==============================|| TESTS ||============================== //

describe("SignalClusterDetailDrawer — TechStack cluster", () => {
  it("renders the tool fields FIRST (TechDetailBlock) then the source signals", () => {
    mockDetail(TECH_CLUSTER, TECH_MEMBERS);
    renderDrawer(TECH_CLUSTER);

    // Tool name renders as the headline (also appears on the t1 member line).
    expect(screen.getAllByText("HubSpot").length).toBeGreaterThanOrEqual(1);
    // Representative tool fields via the shared TechDetailBlock.
    expect(screen.getByText("TOOL USAGE")).toBeInTheDocument();
    expect(screen.getByText("Company-wide")).toBeInTheDocument();
    // The manual Competitor tag was retired — no chip, even though t1 still
    // carries a legacy is_competitor=true.
    expect(screen.queryByText("Competitor")).not.toBeInTheDocument();
    // Then the source-signal list.
    expect(screen.getByText("Signals in this cluster")).toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line")).toHaveLength(2);
  });

  it("hides the priority badge for a tech cluster (neutral LOW floor)", () => {
    mockDetail(TECH_CLUSTER, TECH_MEMBERS);
    renderDrawer(TECH_CLUSTER);
    // 'LOW' -> label 'Low'; it must NOT be surfaced as a priority chip.
    expect(screen.queryByText("Low")).not.toBeInTheDocument();
  });

  it("clicking a source signal REPLACES the content with its tech detail + Back", () => {
    mockDetail(TECH_CLUSTER, TECH_MEMBERS);
    renderDrawer(TECH_CLUSTER);

    // The second member has a unique display name.
    fireEvent.click(screen.getByText("Hubspot CRM"));

    // Member detail shows its source quote; cluster list is replaced.
    expect(
      screen.getByText(/the Hubspot CRM is a bit of a mess/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /back to cluster/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Signals in this cluster")).not.toBeInTheDocument();
    // One drawer only (one Close affordance).
    expect(screen.getAllByLabelText("Close drawer")).toHaveLength(1);

    // Back returns to the cluster view.
    fireEvent.click(screen.getByRole("button", { name: /back to cluster/i }));
    expect(screen.getByText("Signals in this cluster")).toBeInTheDocument();
  });
});

describe("SignalClusterDetailDrawer — priority badge masking is type-conditional", () => {
  it("a pain cluster STILL shows its real priority badge (non-regression guard)", () => {
    // This is the non-vacuity target: masking the badge for ALL types
    // (instead of tech only) makes this assertion fail.
    mockDetail(PAIN_CLUSTER, []);
    renderDrawer(PAIN_CLUSTER);
    expect(screen.getByText("High")).toBeInTheDocument();
  });
});

// frontend/src/__tests__/signals/QualificationGroupedView.test.jsx
//
// B5: the grouped "Qualification" synthesis view. A reusable container
// parameterised by surface (account | dc):
//   Account → qualification clusters + tech stack section
//   DC      → qualification clusters + tech stack + blockers section
//
// Clusters come from the cluster service (useGetClustersByAccount); the typed
// sections (tech / blockers) come from the aggregated endpoint filtered by
// signal_type. The heavy cluster drawer is stubbed here — its own member
// rendering (SignalLine + quote + origin link + reopen) is covered in
// SignalClusterDetailDrawer.grouped.test.jsx.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signalClusters", () => ({
  useGetClustersByAccount: vi.fn(),
  archiveCluster: vi.fn(() => Promise.resolve({ success: true })),
  unarchiveCluster: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("api/signals/aggregatedSignals", () => ({ default: vi.fn() }));

vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: vi.fn(() => ({ choices: {}, choicesLoading: false })),
  validateSignal: vi.fn(() => Promise.resolve({ success: true })),
  reopenSignal: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// Stub the cluster drawer — assert wiring (open + which cluster), not internals.
vi.mock("sections/accounts/signals/SignalClusterDetailDrawer", () => ({
  default: ({ open, clusterSummary }) =>
    open ? (
      <div data-testid="cluster-drawer">{clusterSummary?.canonical_key}</div>
    ) : null,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import QualificationGroupedView from "sections/accounts/signals/QualificationGroupedView";
import { useGetClustersByAccount } from "api/signals/signalClusters";
import useAggregatedSignals from "api/signals/aggregatedSignals";

const ACCOUNT_ID = "acc-1";
const CYCLE_ID = "cycle-1";

const PAIN_CLUSTER = {
  canonical_key: "pain:OPS:TIME",
  signal_type: "pain",
  what: "OPS",
  what_display: "Operations",
  dimension: "TIME",
  dimension_display: "Time",
  summary: "Consolidated pain cluster",
  status: "VALIDATED",
  has_pending_signals: false,
  pending_count: 0,
  confirmation_count: 2,
  distinct_contacts_count: 2,
  first_observed_at: "2026-04-01T10:00:00Z",
  last_confirmed_at: "2026-05-01T10:00:00Z",
  freshness_status: "FRESH",
  priority_score: 80,
  priority_bucket: "HIGH",
  human_impacts: [],
  metrics: [],
  target_dates: [],
  decision_cycle_ids: [],
  campaign_ids: [],
  is_archived: false,
};

const TECH = [
  { id: "t1", status: "PENDING", tech_name: "Snowflake", _signalType: "tech-stack" },
];
const BLOCKERS = [
  { id: "b1", status: "PENDING", summary: "Budget frozen Q4", _signalType: "blockers" },
];

function sectionReturn(signals) {
  return {
    signals,
    count: signals.length,
    next: null,
    previous: null,
    pageCount: 1,
    loading: false,
    validating: false,
    error: null,
    mutate: vi.fn(),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  useGetClustersByAccount.mockReturnValue({
    clusters: [PAIN_CLUSTER],
    clustersCount: 1,
    clustersLoading: false,
    clustersError: null,
    mutateClusters: vi.fn(),
  });
  useAggregatedSignals.mockImplementation(({ signalTypes } = {}) => {
    if (signalTypes?.includes("tech-stack")) return sectionReturn(TECH);
    if (signalTypes?.includes("blockers")) return sectionReturn(BLOCKERS);
    return sectionReturn([]);
  });
});

afterEach(() => cleanup());

describe("QualificationGroupedView — Account surface", () => {
  it("renders qualification cluster cards + a Tech Stack section, NO Blockers", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);

    expect(screen.getByText("Consolidated pain cluster")).toBeInTheDocument();
    // "Tech Stack" appears both as the section header and the type chip;
    // assert the section by its content instead.
    expect(screen.getByText("Snowflake")).toBeInTheDocument();
    // Blockers section must not exist on the Account surface (the "Blockers"
    // header would be the only source of that text — the chip label is "Blocker").
    expect(screen.queryByText("Blockers")).not.toBeInTheDocument();
    expect(screen.queryByText("Budget frozen Q4")).not.toBeInTheDocument();
  });

  it("shows the cluster freshness/lifecycle on the card", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.getByText("Fresh")).toBeInTheDocument();
  });

  it("fetches the tech section via the aggregated endpoint with signal_type=[tech-stack]", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    const techCall = useAggregatedSignals.mock.calls.find((c) =>
      c[0]?.signalTypes?.includes("tech-stack"),
    );
    expect(techCall).toBeTruthy();
    expect(techCall[0].accountId).toBe(ACCOUNT_ID);
  });

  it("scopes clusters to the account (no decisionCycleId)", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    const args = useGetClustersByAccount.mock.calls.at(-1);
    expect(args[0]).toBe(ACCOUNT_ID);
    expect(args[1].signalType).toEqual(["pain", "objective", "impact"]);
    expect(args[1].decisionCycleId).toBeUndefined();
  });

  it("opens the cluster drawer when a cluster card is clicked", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.queryByTestId("cluster-drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Consolidated pain cluster"));
    expect(screen.getByTestId("cluster-drawer")).toHaveTextContent("pain:OPS:TIME");
  });
});

describe("QualificationGroupedView — DC surface", () => {
  it("renders clusters + Tech Stack + a Blockers section", () => {
    render(
      <QualificationGroupedView
        surface="dc"
        accountId={ACCOUNT_ID}
        decisionCycleId={CYCLE_ID}
      />,
    );

    expect(screen.getByText("Consolidated pain cluster")).toBeInTheDocument();
    expect(screen.getByText("Snowflake")).toBeInTheDocument();
    // "Blockers" is the section header (the chip label is the singular "Blocker").
    expect(screen.getByText("Blockers")).toBeInTheDocument();
    expect(screen.getByText("Budget frozen Q4")).toBeInTheDocument();
  });

  it("scopes clusters + tech + blockers to the decision cycle", () => {
    render(
      <QualificationGroupedView
        surface="dc"
        accountId={ACCOUNT_ID}
        decisionCycleId={CYCLE_ID}
      />,
    );

    const clusterArgs = useGetClustersByAccount.mock.calls.at(-1);
    expect(clusterArgs[1].decisionCycleId).toBe(CYCLE_ID);

    const blockerCall = useAggregatedSignals.mock.calls.find((c) =>
      c[0]?.signalTypes?.includes("blockers"),
    );
    expect(blockerCall).toBeTruthy();
    expect(blockerCall[0].decisionCycleId).toBe(CYCLE_ID);
  });
});

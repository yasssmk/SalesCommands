// frontend/src/__tests__/signals/QualificationGroupedView.test.jsx
//
// C4: the rich DC/Account Qualification view — three narrative sections
// (Objectives / Pains / Impacts), each nesting the account's (or cycle's)
// clusters by domain → dimension → cluster rows. One row = one cluster with
// EPURATED factual meta (signal count, "N to validate", freshness, covered
// period, departments, and Account-only DC count). No urgency / max-level /
// impacted-contacts. Tech + Objections are out of scope here.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signalClusters", () => ({
  useGetClustersByAccount: vi.fn(),
}));

vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: vi.fn(() => ({ choices: {}, choicesLoading: false })),
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

const ACCOUNT_ID = "acc-1";
const CYCLE_ID = "cycle-1";

const PAIN_CLUSTER = {
  canonical_key: "pain:OPS:TIME",
  signal_type: "pain",
  what: "OPS",
  what_display: "Operations",
  dimension: "TIME",
  dimension_display: "Time",
  summary: "Reporting is slow",
  signal_count: 5,
  pending_count: 2,
  freshness_status: "FRESH",
  period_start: "2026-04-01T10:00:00Z",
  period_end: "2026-05-01T10:00:00Z",
  departments: [{ id: "1", name: "Marketing & Communications" }],
  decision_cycle_ids: ["dc1", "dc2"],
  // Fields the epurated row must NOT surface:
  priority_bucket: "HIGH",
  max_scope_level: "BUSINESS",
  distinct_contacts_count: 3,
};

const OBJECTIVE_CLUSTER = {
  canonical_key: "objective:GROWTH:SCALE",
  signal_type: "objective",
  what: "GROWTH",
  what_display: "Growth",
  dimension: "SCALE",
  dimension_display: "Scale",
  summary: "Grow the pipeline",
  signal_count: 1,
  pending_count: 0,
  freshness_status: "DORMANT",
  period_start: "2026-03-01T10:00:00Z",
  period_end: "2026-03-01T10:00:00Z",
  departments: [],
  decision_cycle_ids: ["dc1"],
};

function mockClusters(list) {
  useGetClustersByAccount.mockReturnValue({
    clusters: list,
    clustersCount: list.length,
    clustersLoading: false,
    clustersError: null,
    mutateClusters: vi.fn(),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockClusters([OBJECTIVE_CLUSTER, PAIN_CLUSTER]);
});

afterEach(() => cleanup());

describe("QualificationGroupedView — three narrative sections", () => {
  it("renders Objectives / Pains / Impacts, nested by domain → dimension", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);

    // Section headers.
    expect(screen.getByText("Objectives")).toBeInTheDocument();
    expect(screen.getByText("Pains")).toBeInTheDocument();
    expect(screen.getByText("Impacts")).toBeInTheDocument();

    // Domain sub-heading + dimension under the Pains section.
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Time")).toBeInTheDocument();

    // One cluster row per cluster.
    expect(screen.getByText("Reporting is slow")).toBeInTheDocument();
    expect(screen.getByText("Grow the pipeline")).toBeInTheDocument();
  });

  it("shows epurated meta on the row and NOT urgency / max-level / impacted contacts", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);

    // Epurated meta present.
    expect(screen.getByText("5 signals")).toBeInTheDocument();
    expect(screen.getByText("2 to validate")).toBeInTheDocument();
    expect(screen.getByText("Fresh")).toBeInTheDocument();
    expect(screen.getByText(/→/)).toBeInTheDocument(); // covered period
    expect(screen.getByText("Marketing & Communications")).toBeInTheDocument();

    // Excluded concepts.
    expect(screen.queryByText("High")).not.toBeInTheDocument(); // priority/urgency
    expect(screen.queryByText("Business")).not.toBeInTheDocument(); // max scope level
    expect(screen.queryByText(/impacted contacts/i)).not.toBeInTheDocument();
  });

  it("Account surface shows the DC count on the row", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.getByText("2 DCs")).toBeInTheDocument();
  });

  it("DC surface hides the DC count on the row", () => {
    render(
      <QualificationGroupedView
        surface="dc"
        accountId={ACCOUNT_ID}
        decisionCycleId={CYCLE_ID}
      />,
    );
    expect(screen.queryByText("2 DCs")).not.toBeInTheDocument();
    // The cluster itself still renders.
    expect(screen.getByText("Reporting is slow")).toBeInTheDocument();
  });

  it("opens the cluster drawer when a cluster row is clicked", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.queryByTestId("cluster-drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Reporting is slow"));
    expect(screen.getByTestId("cluster-drawer")).toHaveTextContent("pain:OPS:TIME");
  });

  it("renders a neutral empty state for a section with no clusters", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    // No impact clusters seeded → the Impacts section shows a neutral note.
    expect(screen.getByText("No impacts yet")).toBeInTheDocument();
  });

  it("scopes clusters to the account (no decisionCycleId) and to the cycle on DC", () => {
    const { unmount } = render(
      <QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />,
    );
    let args = useGetClustersByAccount.mock.calls.at(-1);
    expect(args[0]).toBe(ACCOUNT_ID);
    expect(args[1].signalType).toEqual(["objective", "pain", "impact"]);
    expect(args[1].decisionCycleId).toBeUndefined();
    unmount();

    render(
      <QualificationGroupedView
        surface="dc"
        accountId={ACCOUNT_ID}
        decisionCycleId={CYCLE_ID}
      />,
    );
    args = useGetClustersByAccount.mock.calls.at(-1);
    expect(args[1].decisionCycleId).toBe(CYCLE_ID);
  });

  it("renders the global empty state when there are no clusters at all", () => {
    mockClusters([]);
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.getByText("No qualification clusters yet")).toBeInTheDocument();
  });
});

// frontend/src/__tests__/signals/QualificationGroupedView.test.jsx
//
// C4 + C4-fix: the rich DC/Account Qualification view. Three narrative
// sections (Objectives / Pains / Impacts) nested domain → dimension → cluster
// rows, plus Tech Stack and Objections placement sections. All sections are
// collapsible (open by default); rows are informational.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signalClusters", () => ({
  useGetClustersByAccount: vi.fn(),
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

// Stub the drawers/modals — assert wiring, not internals.
vi.mock("sections/accounts/signals/SignalClusterDetailDrawer", () => ({
  default: ({ open, clusterSummary }) =>
    open ? (
      <div data-testid="cluster-drawer">{clusterSummary?.canonical_key}</div>
    ) : null,
}));
vi.mock("sections/accounts/signals/AlertSignalReject", () => ({ default: () => null }));
vi.mock("sections/accounts/signals/SignalEditDialog", () => ({ default: () => null }));
vi.mock("sections/activities/signals/SignalQuickDrawer", () => ({ default: () => null }));

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
  summary: "Reporting is slow",
  signal_count: 5,
  pending_count: 2,
  freshness_status: "FRESH",
  period_start: "2026-04-01T10:00:00Z",
  period_end: "2026-05-01T10:00:00Z",
  departments: [{ id: "1", name: "Marketing & Communications" }],
  decision_cycle_ids: ["dc1", "dc2"],
  priority_bucket: "HIGH",
  max_scope_level: "BUSINESS",
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

const TECH = [{ id: "t1", status: "PENDING", tech_name: "Snowflake", _signalType: "tech-stack" }];
const BLOCKERS = [{ id: "b1", status: "PENDING", summary: "Budget frozen Q4", _signalType: "blockers" }];

function sectionReturn(signals) {
  return {
    signals,
    count: signals.length,
    loading: false,
    error: null,
    mutate: vi.fn(),
  };
}

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
  useAggregatedSignals.mockImplementation(({ signalTypes } = {}) => {
    if (signalTypes?.includes("tech-stack")) return sectionReturn(TECH);
    if (signalTypes?.includes("blockers")) return sectionReturn(BLOCKERS);
    return sectionReturn([]);
  });
});

afterEach(() => cleanup());

describe("QualificationGroupedView — sections + nesting", () => {
  it("renders Objectives / Pains / Impacts nested by domain → dimension", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.getByText("Objectives")).toBeInTheDocument();
    expect(screen.getByText("Pains")).toBeInTheDocument();
    expect(screen.getByText("Impacts")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument(); // domain
    expect(screen.getByText("Time")).toBeInTheDocument(); // dimension
    expect(screen.getByText("Reporting is slow")).toBeInTheDocument();
    expect(screen.getByText("Grow the pipeline")).toBeInTheDocument();
  });

  it("shows epurated meta and NOT urgency / max-level / impacted contacts", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.getByText("5 signals")).toBeInTheDocument();
    expect(screen.getByText("2 to validate")).toBeInTheDocument();
    expect(screen.getByText("Fresh")).toBeInTheDocument();
    expect(screen.getByText(/→/)).toBeInTheDocument();
    expect(screen.getByText("Marketing & Communications")).toBeInTheDocument();
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.queryByText("Business")).not.toBeInTheDocument();
  });

  it("Account shows the DC count; DC hides it", () => {
    const { unmount } = render(
      <QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />,
    );
    expect(screen.getByText("2 DCs")).toBeInTheDocument();
    unmount();
    render(
      <QualificationGroupedView surface="dc" accountId={ACCOUNT_ID} decisionCycleId={CYCLE_ID} />,
    );
    expect(screen.queryByText("2 DCs")).not.toBeInTheDocument();
  });

  it("opens the cluster drawer when a cluster row is clicked", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.queryByTestId("cluster-drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Reporting is slow"));
    expect(screen.getByTestId("cluster-drawer")).toHaveTextContent("pain:OPS:TIME");
  });
});

describe("QualificationGroupedView — collapsible sections (open by default)", () => {
  it("sections and domains are OPEN by default (content visible on first render)", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    // Cluster row + department chip are visible without any interaction.
    expect(screen.getByText("Reporting is slow")).toBeInTheDocument();
    expect(screen.getByText("Marketing & Communications")).toBeInTheDocument();
  });

  it("clicking a section header toggles it (open → closed → open)", () => {
    // The MUI Accordion summary flips aria-expanded on each click. (jsdom does
    // not fire transitionend, so unmount-on-collapse can't be asserted here;
    // aria-expanded is the reliable open/closed signal.)
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    const header = screen.getByRole("button", { name: /Pains/i });

    expect(header).toHaveAttribute("aria-expanded", "true"); // open by default
    fireEvent.click(header);
    expect(header).toHaveAttribute("aria-expanded", "false"); // collapsed
    fireEvent.click(header);
    expect(header).toHaveAttribute("aria-expanded", "true"); // expanded again
  });

  it("a domain group inside a section toggles too", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    const domainHeader = screen.getByRole("button", { name: /Operations/i });
    expect(domainHeader).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(domainHeader);
    expect(domainHeader).toHaveAttribute("aria-expanded", "false");
  });
});

describe("QualificationGroupedView — Tech + Objections placement", () => {
  it("Account surface shows Tech Stack but NOT Objections", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.getByText("Tech Stack")).toBeInTheDocument();
    expect(screen.getByText("Snowflake")).toBeInTheDocument();
    expect(screen.queryByText("Objections")).not.toBeInTheDocument();
    expect(screen.queryByText("Budget frozen Q4")).not.toBeInTheDocument();
  });

  it("DC surface shows Tech Stack AND Objections", () => {
    render(
      <QualificationGroupedView surface="dc" accountId={ACCOUNT_ID} decisionCycleId={CYCLE_ID} />,
    );
    expect(screen.getByText("Tech Stack")).toBeInTheDocument();
    expect(screen.getByText("Objections")).toBeInTheDocument();
    expect(screen.getByText("Budget frozen Q4")).toBeInTheDocument();
  });

  it("shows Tech/Objections placement even when there are no clusters", () => {
    mockClusters([]);
    render(
      <QualificationGroupedView surface="dc" accountId={ACCOUNT_ID} decisionCycleId={CYCLE_ID} />,
    );
    // Narrative sections still present (neutral empty), and placement sections show.
    expect(screen.getByText("Objectives")).toBeInTheDocument();
    expect(screen.getByText("No objectives yet")).toBeInTheDocument();
    expect(screen.getByText("Tech Stack")).toBeInTheDocument();
    expect(screen.getByText("Objections")).toBeInTheDocument();
  });
});

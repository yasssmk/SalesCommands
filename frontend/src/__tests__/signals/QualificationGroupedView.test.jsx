// frontend/src/__tests__/signals/QualificationGroupedView.test.jsx
//
// C4 + C4-fix: the rich DC/Account Qualification view. Three narrative
// sections (Objectives / Pains / Impacts) nested domain → dimension → cluster
// rows, plus Tech Stack and Objections placement sections. All sections are
// collapsible (open by default); rows are informational.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import AccordionOverride from "themes/overrides/Accordion";
import AccordionSummaryOverride from "themes/overrides/AccordionSummary";
import AccordionDetailsOverride from "themes/overrides/AccordionDetails";

// A theme carrying the project's Accordion overrides (tinted summary +
// RightOutlined expand chevron), so the themed accordion renders in tests.
// Only the Accordion overrides are wired (avoids the font-loading chain in
// the full theme index).
const themed = createTheme({
  palette: { secondary: { lighter: "#f4f6f8", light: "#d9d9d9", main: "#8c8c8c" } },
});
themed.components = {
  ...AccordionOverride(themed),
  ...AccordionSummaryOverride(themed),
  ...AccordionDetailsOverride(themed),
};
const renderThemed = (ui) => render(<ThemeProvider theme={themed}>{ui}</ThemeProvider>);

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

// Tech is now a CLUSTER (right column, cluster pipeline), not a flat signal.
const TECH_CLUSTER = {
  canonical_key: "hubspot",
  signal_type: "tech_stack",
  what: null,
  what_display: null,
  dimension: null,
  dimension_display: null,
  summary: "HubSpot",
  signal_count: 3,
  pending_count: 0,
  freshness_status: "FRESH",
  period_start: "2026-04-01T10:00:00Z",
  period_end: "2026-05-01T10:00:00Z",
  last_confirmed_at: "2026-05-01T10:00:00Z",
  departments: [],
  decision_cycle_ids: [],
  priority_bucket: "LOW",
};

// Constraint is a CLUSTER too (right column, DC-scoped), grouped by nature —
// canonical_key IS the nature code.
const CONSTRAINT_CLUSTER = {
  canonical_key: "CONTRACTUAL",
  signal_type: "constraint",
  what: null,
  what_display: null,
  dimension: null,
  dimension_display: null,
  summary: "GDPR compliance is mandatory",
  signal_count: 2,
  pending_count: 0,
  freshness_status: "FRESH",
  period_start: "2026-04-01T10:00:00Z",
  period_end: "2026-05-01T10:00:00Z",
  last_confirmed_at: "2026-05-01T10:00:00Z",
  departments: [],
  decision_cycle_ids: ["dc1"],
  priority_bucket: "LOW",
};

// Objections are still flat (out of scope for the tech-cluster sprint).
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
  // The tech cluster rides in the SAME cluster list as the narrative types.
  mockClusters([OBJECTIVE_CLUSTER, PAIN_CLUSTER, TECH_CLUSTER]);
  // Only Objections still uses the flat aggregated path now.
  useAggregatedSignals.mockImplementation(({ signalTypes } = {}) => {
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

describe("QualificationGroupedView — no Type filter in grouped", () => {
  it("always fetches the full clusterable set and shows every section", () => {
    render(
      <QualificationGroupedView
        surface="dc"
        accountId={ACCOUNT_ID}
        decisionCycleId={CYCLE_ID}
      />,
    );
    // Cluster fetch covers all clusterable types, tech + constraint included
    // (one fetch). Constraint is added on the DC surface (DC-scoped type).
    const args = useGetClustersByAccount.mock.calls.at(-1);
    expect(args[1].signalType).toEqual([
      "objective",
      "pain",
      "impact",
      "tech_stack",
      "constraint",
    ]);
    // All narrative sections + Tech/Objections render.
    expect(screen.getByText("Objectives")).toBeInTheDocument();
    expect(screen.getByText("Pains")).toBeInTheDocument();
    expect(screen.getByText("Impacts")).toBeInTheDocument();
    expect(screen.getByText("Tech Stack")).toBeInTheDocument();
    expect(screen.getByText("Objections")).toBeInTheDocument();
  });
});

describe("QualificationGroupedView — two-column layout (same as Activity)", () => {
  it("renders narrative sections LEFT and Tech/Objections RIGHT", () => {
    const { container } = render(
      <QualificationGroupedView surface="dc" accountId={ACCOUNT_ID} decisionCycleId={CYCLE_ID} />,
    );
    const cols = container.querySelectorAll(".MuiGrid-container > .MuiGrid-item");
    expect(cols).toHaveLength(2);
    const [left, right] = cols;

    // Left = narrative sections, with domain → dimension → cluster nesting.
    expect(left).toHaveTextContent("Objectives");
    expect(left).toHaveTextContent("Pains");
    expect(left).toHaveTextContent("Impacts");
    expect(left).toHaveTextContent("Operations"); // domain sub-heading
    expect(left).toHaveTextContent("Reporting is slow"); // cluster row

    // Right = Tech Stack + Objections (flat).
    expect(right).toHaveTextContent("Tech Stack");
    expect(right).toHaveTextContent("Objections");
  });

  it("Account keeps the two columns but has no Objections on the right", () => {
    const { container } = render(
      <QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />,
    );
    const cols = container.querySelectorAll(".MuiGrid-container > .MuiGrid-item");
    expect(cols).toHaveLength(2);
    expect(cols[1]).toHaveTextContent("Tech Stack");
    expect(cols[1]).not.toHaveTextContent("Objections");
  });
});

describe("QualificationGroupedView — Constraints section (DC only, by nature)", () => {
  it("renders the Constraints section grouped by nature in DC", () => {
    mockClusters([OBJECTIVE_CLUSTER, PAIN_CLUSTER, TECH_CLUSTER, CONSTRAINT_CLUSTER]);
    render(
      <QualificationGroupedView surface="dc" accountId={ACCOUNT_ID} decisionCycleId={CYCLE_ID} />,
    );
    expect(screen.getByText("Constraints")).toBeInTheDocument();
    // Nature group header (CONTRACTUAL -> "Contractual & Legal") + the cluster row.
    expect(screen.getByText("Contractual & Legal")).toBeInTheDocument();
    expect(screen.getByText("GDPR compliance is mandatory")).toBeInTheDocument();
  });

  it("does NOT render Constraints on the account surface", () => {
    mockClusters([OBJECTIVE_CLUSTER, PAIN_CLUSTER, TECH_CLUSTER]);
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.queryByText("Constraints")).not.toBeInTheDocument();
    // And the fetch did NOT request constraint at account level.
    const args = useGetClustersByAccount.mock.calls.at(-1);
    expect(args[1].signalType).not.toContain("constraint");
  });

  it("opens the cluster drawer when a constraint row is clicked", () => {
    mockClusters([CONSTRAINT_CLUSTER]);
    render(
      <QualificationGroupedView surface="dc" accountId={ACCOUNT_ID} decisionCycleId={CYCLE_ID} />,
    );
    expect(screen.queryByTestId("cluster-drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("GDPR compliance is mandatory"));
    expect(screen.getByTestId("cluster-drawer")).toBeInTheDocument();
  });

  it("passes the nature filter to the cluster fetch on the DC surface", () => {
    mockClusters([CONSTRAINT_CLUSTER]);
    render(
      <QualificationGroupedView
        surface="dc"
        accountId={ACCOUNT_ID}
        decisionCycleId={CYCLE_ID}
        natures={["TECHNICAL"]}
      />,
    );
    const opts = useGetClustersByAccount.mock.calls.at(-1)[1];
    expect(opts.natures).toEqual(["TECHNICAL"]);
  });

  it("does NOT send the nature filter on the account surface (constraints are DC-only)", () => {
    mockClusters([OBJECTIVE_CLUSTER, PAIN_CLUSTER, TECH_CLUSTER]);
    render(
      <QualificationGroupedView
        surface="account"
        accountId={ACCOUNT_ID}
        natures={["TECHNICAL"]}
      />,
    );
    const opts = useGetClustersByAccount.mock.calls.at(-1)[1];
    expect(opts.natures).toBeUndefined();
  });
});

describe("QualificationGroupedView — themed MUI Accordion", () => {
  it("renders sections as MUI Accordions with the themed expand chevron", () => {
    const { container } = renderThemed(
      <QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />,
    );
    // Themed MUI Accordion markup — not a hand-rolled bordered box.
    expect(container.querySelectorAll(".MuiAccordion-root").length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".MuiAccordionSummary-root").length).toBeGreaterThan(0);
    // The theme supplies the expand-icon (chevron) wrapper.
    expect(
      container.querySelectorAll(".MuiAccordionSummary-expandIconWrapper").length,
    ).toBeGreaterThan(0);
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
    // Tech renders as a cluster row (one techno = one line), not a flat signal.
    expect(screen.getByText("HubSpot")).toBeInTheDocument();
    expect(screen.queryByText("Objections")).not.toBeInTheDocument();
    expect(screen.queryByText("Budget frozen Q4")).not.toBeInTheDocument();
  });

  it("DC surface shows Tech Stack AND Objections", () => {
    render(
      <QualificationGroupedView surface="dc" accountId={ACCOUNT_ID} decisionCycleId={CYCLE_ID} />,
    );
    expect(screen.getByText("Tech Stack")).toBeInTheDocument();
    expect(screen.getByText("HubSpot")).toBeInTheDocument();
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
    expect(screen.getByText("No tech stack signals captured")).toBeInTheDocument();
    expect(screen.getByText("Objections")).toBeInTheDocument();
  });
});

describe("QualificationGroupedView — Tech Stack clustered right column", () => {
  it("renders the tech cluster as a ClusterRow (one techno = one row) on Account", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    // NON-VACUITY TARGET: bucketing tech on a non-matching signal_type empties
    // the section and this assertion fails.
    expect(screen.getByText("HubSpot")).toBeInTheDocument();
    // Epurated tech row: count + last confirmation (ClusterRow tech branch).
    expect(screen.getByText("3 signals")).toBeInTheDocument();
    expect(screen.getByText(/Last confirmed/)).toBeInTheDocument();
  });

  it("renders the tech cluster on the DC surface too", () => {
    render(
      <QualificationGroupedView surface="dc" accountId={ACCOUNT_ID} decisionCycleId={CYCLE_ID} />,
    );
    expect(screen.getByText("HubSpot")).toBeInTheDocument();
  });

  it("clicking a tech cluster row opens the CLUSTER drawer (not the flat quick-drawer)", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    expect(screen.queryByTestId("cluster-drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("HubSpot"));
    // The stubbed cluster drawer echoes the cluster's canonical_key.
    expect(screen.getByTestId("cluster-drawer")).toHaveTextContent("hubspot");
  });

  it("tech goes through the cluster pipeline — no flat 'tech-stack' aggregated fetch", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    const techStackFetches = useAggregatedSignals.mock.calls.filter(
      ([opts]) => opts?.signalTypes?.includes("tech-stack"),
    );
    expect(techStackFetches).toHaveLength(0);
  });
});

describe("QualificationGroupedView — Qualification filters forwarded to the cluster fetch", () => {
  it("forwards perimeter, what, dimension, contacts and statuses to the cluster endpoint", () => {
    render(
      <QualificationGroupedView
        surface="account"
        accountId={ACCOUNT_ID}
        perimeter={["BUSINESS", "42"]}
        whats={["DATA"]}
        dimensions={["QUALITY"]}
        contacts={["contact-9"]}
        statuses={["PENDING", "VALIDATED"]}
      />,
    );
    const opts = useGetClustersByAccount.mock.calls.at(-1)[1];
    expect(opts.perimeter).toEqual(["BUSINESS", "42"]);
    expect(opts.whats).toEqual(["DATA"]);
    expect(opts.dimensions).toEqual(["QUALITY"]);
    expect(opts.contacts).toEqual(["contact-9"]);
    expect(opts.statuses).toEqual(["PENDING", "VALIDATED"]);
  });

  it("omits the Qualification filters when none are set", () => {
    render(<QualificationGroupedView surface="account" accountId={ACCOUNT_ID} />);
    const opts = useGetClustersByAccount.mock.calls.at(-1)[1];
    expect(opts.perimeter).toBeUndefined();
    expect(opts.whats).toBeUndefined();
    expect(opts.dimensions).toBeUndefined();
    expect(opts.contacts).toBeUndefined();
  });
});

// frontend/src/__tests__/signals/SignalClusterDetailDrawer.grouped.test.jsx
//
// B5: the cluster drill-down drawer now renders its members as the shared
// SignalLine (same as the flat views), with full CRUD including reopen, and
// opens the shared SignalQuickDrawer (source quote + origin-activity link)
// when a member is clicked.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
vi.mock("components/signals/SignalEditDrawer", () => ({ default: () => null }));
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

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
import { reopenSignal } from "api/signals/signals";

const CLUSTER_SUMMARY = {
  canonical_key: "pain:OPS:TIME",
  signal_type: "pain",
  what: "OPS",
  what_display: "Operations",
  dimension: "TIME",
  dimension_display: "Time",
  summary: "Consolidated pain",
  priority_bucket: "HIGH",
  freshness_status: "FRESH",
  status: "VALIDATED",
  confirmation_count: 2,
  distinct_contacts_count: 2,
  last_confirmed_at: "2026-05-01T10:00:00Z",
  human_impacts: [],
  metrics: [],
  decision_cycle_ids: [],
  is_archived: false,
};

const MEMBERS = [
  {
    id: "m1",
    status: "PENDING",
    summary: "Pending pain member",
    what: "OPS",
    what_display: "Operations",
    dimension: "TIME",
    dimension_display: "Time",
    source_quote: "we lose five hours every week",
    source_context: { activity: { id: "act-1" }, contacts: [] },
  },
  {
    id: "m2",
    status: "REJECTED",
    summary: "Rejected pain member",
    what: "OPS",
    dimension: "TIME",
  },
];

function renderDrawer(props = {}) {
  return render(
    <SignalClusterDetailDrawer
      open
      onClose={vi.fn()}
      clusterSummary={CLUSTER_SUMMARY}
      accountId="acc-1"
      choices={{}}
      choicesLoading={false}
      onClusterChange={vi.fn()}
      {...props}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useGetClusterDetail.mockReturnValue({
    cluster: { ...CLUSTER_SUMMARY, members: MEMBERS },
    clusterLoading: false,
    clusterError: null,
    mutateCluster: vi.fn(),
  });
});

afterEach(() => cleanup());

describe("SignalClusterDetailDrawer — grouped member rendering", () => {
  it("renders members as shared SignalLine rows", () => {
    renderDrawer();
    expect(screen.getAllByTestId("signal-line")).toHaveLength(2);
    expect(screen.getByText("Pending pain member")).toBeInTheDocument();
    expect(screen.getByText("Rejected pain member")).toBeInTheDocument();
  });

  it("opens the member quick-drawer with source quote + origin-activity link", () => {
    renderDrawer();
    expect(screen.queryByText(/View origin activity/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Pending pain member"));

    // SourceQuoteBlock wraps the quote in typographic quotes, so match loosely.
    expect(screen.getByText(/we lose five hours every week/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /View origin activity/i })).toBeInTheDocument();
  });

  it("reopens a rejected member from its quick-drawer (no action on the row)", async () => {
    renderDrawer();
    // The member row carries no action button.
    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();
    // Click the rejected member row to open its quick-drawer, then reopen there.
    fireEvent.click(screen.getByText("Rejected pain member"));
    const reopenBtn = screen.getByRole("button", { name: /reopen/i });
    await act(async () => {
      fireEvent.click(reopenBtn);
    });
    expect(reopenSignal).toHaveBeenCalledWith("pain", "m2");
  });
});

describe("SignalClusterDetailDrawer — one drawer, replace + back (C5)", () => {
  it("opening a cluster shows the cluster view (members list)", () => {
    renderDrawer();
    expect(screen.getByText("Signals in this cluster")).toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line")).toHaveLength(2);
    // No signal-detail markers yet.
    expect(screen.queryByRole("button", { name: /back to cluster/i })).not.toBeInTheDocument();
  });

  it("clicking a member REPLACES the content with its signal detail (one drawer, not stacked)", () => {
    renderDrawer();
    fireEvent.click(screen.getByText("Pending pain member"));

    // Signal detail present ...
    expect(screen.getByText(/we lose five hours every week/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to cluster/i })).toBeInTheDocument();
    // ... and the cluster view is GONE (replaced, not stacked underneath).
    expect(screen.queryByText("Signals in this cluster")).not.toBeInTheDocument();
    expect(screen.queryAllByTestId("signal-line")).toHaveLength(0);
    // Exactly one drawer (one Close affordance).
    expect(screen.getAllByLabelText("Close drawer")).toHaveLength(1);
  });

  it("the Back affordance returns to the cluster view", () => {
    renderDrawer();
    fireEvent.click(screen.getByText("Pending pain member"));
    expect(screen.queryByText("Signals in this cluster")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /back to cluster/i }));

    // Back on the cluster view; signal detail gone.
    expect(screen.getByText("Signals in this cluster")).toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /back to cluster/i })).not.toBeInTheDocument();
  });

  it("the in-drawer signal detail carries the actions (validate/reject/edit)", () => {
    renderDrawer();
    fireEvent.click(screen.getByText("Pending pain member"));
    expect(screen.getByRole("button", { name: /validate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });
});

describe("SignalClusterDetailDrawer — removed residuals", () => {
  it("has no Archive / Unarchive cluster button", () => {
    renderDrawer();
    expect(
      screen.queryByRole("button", { name: /archive cluster/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /unarchive cluster/i }),
    ).not.toBeInTheDocument();
  });

  it("shows no 'Max level' meta on a pain cluster", () => {
    renderDrawer();
    expect(screen.queryByText("Max level")).not.toBeInTheDocument();
  });

  it("shows no 'Max scope' meta on an objective cluster", () => {
    const objective = {
      ...CLUSTER_SUMMARY,
      canonical_key: "objective:GROWTH:SCALE",
      signal_type: "objective",
      max_scope_level: "BUSINESS",
      target_dates: [],
    };
    useGetClusterDetail.mockReturnValue({
      cluster: { ...objective, members: [] },
      clusterLoading: false,
      clusterError: null,
      mutateCluster: vi.fn(),
    });
    renderDrawer({ clusterSummary: objective });
    expect(screen.queryByText("Max scope")).not.toBeInTheDocument();
  });
});

// frontend/src/__tests__/signals/ActivityGroupedFilters.test.jsx
//
// The Activity grouped view applies the Qualification filters CLIENT-SIDE (no
// cluster endpoint) before grouping: perimeter (OR), what, dimension, contact,
// status. Empty result → neutral section, never an error surface.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("hooks/useActivityAllSignals", () => ({
  default: vi.fn(),
}));

vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: vi.fn(() => ({ choices: {}, choicesLoading: false })),
  validateSignal: vi.fn(),
  rejectSignal: vi.fn(),
  reopenSignal: vi.fn(),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// Drawer / dialog are irrelevant here — stub to null.
vi.mock("components/signals/SignalQuickDrawer", () => ({ default: () => null }));
vi.mock("components/signals/SignalEditDrawer", () => ({ default: () => null }));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivityQualificationTab from "sections/activities/workspace/ActivityQualificationTab";
import useActivityAllSignals from "hooks/useActivityAllSignals";

const MOCK_ACTIVITY = { id: "act-1", account: "acc-1" };

// Three qualification signals with distinct perimeter / domain / dimension.
const OBJ_BIZ_DATA = {
  id: "o1", status: "VALIDATED", summary: "Objective biz data",
  what: "DATA", dimension: "QUALITY", scope_level: "BUSINESS",
  target_department: null, source_context: { contacts: [{ id: "c1" }] },
  _signalType: "objective",
};
const PAIN_MKTG_OPS = {
  id: "p1", status: "PENDING", summary: "Pain marketing ops",
  what: "OPS", dimension: "TIME", scope_level: "DEPARTMENT",
  target_department: { id: "3", name: "Marketing" },
  source_context: { contacts: [{ id: "c2" }] }, _signalType: "pain",
};
const IMPACT_FIN_GROWTH = {
  id: "i1", status: "PENDING", summary: "Impact finance growth",
  what: "GROWTH", dimension: "COST", scope_level: "DEPARTMENT",
  target_department: { id: "5", name: "Finance" },
  source_context: { contacts: [{ id: "c3" }] }, _signalType: "impact",
};

function mockSignals() {
  useActivityAllSignals.mockReturnValue({
    qualificationSignals: [OBJ_BIZ_DATA, PAIN_MKTG_OPS, IMPACT_FIN_GROWTH],
    techStackSignals: [],
    blockerSignals: [],
    loading: false,
    error: null,
    mutateAll: vi.fn(),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSignals();
});
afterEach(() => cleanup());

function renderTab(groupedFilters) {
  render(
    <ActivityQualificationTab activity={MOCK_ACTIVITY} groupedFilters={groupedFilters} />,
  );
}

describe("Activity grouped view — client-side Qualification filters", () => {
  it("shows all qualification signals with no filter", () => {
    renderTab({});
    expect(screen.getByText("Objective biz data")).toBeInTheDocument();
    expect(screen.getByText("Pain marketing ops")).toBeInTheDocument();
    expect(screen.getByText("Impact finance growth")).toBeInTheDocument();
  });

  it("perimeter=[Business, Marketing] keeps scope=BUSINESS OR target=Marketing", () => {
    renderTab({ perimeter: ["BUSINESS", "3"] });
    expect(screen.getByText("Objective biz data")).toBeInTheDocument(); // BUSINESS
    expect(screen.getByText("Pain marketing ops")).toBeInTheDocument(); // Marketing
    // Finance (dept 5) is excluded by the perimeter.
    expect(screen.queryByText("Impact finance growth")).not.toBeInTheDocument();
  });

  it("what=[DATA] keeps only DATA-domain signals", () => {
    renderTab({ whats: ["DATA"] });
    expect(screen.getByText("Objective biz data")).toBeInTheDocument();
    expect(screen.queryByText("Pain marketing ops")).not.toBeInTheDocument();
    expect(screen.queryByText("Impact finance growth")).not.toBeInTheDocument();
  });

  it("dimension=[QUALITY] keeps only QUALITY signals", () => {
    renderTab({ dimensions: ["QUALITY"] });
    expect(screen.getByText("Objective biz data")).toBeInTheDocument();
    expect(screen.queryByText("Pain marketing ops")).not.toBeInTheDocument();
  });

  it("an emptied-out section stays neutral (not an error surface)", () => {
    // what=[DATA] keeps the Objective; the Pains / Impacts sections empty out
    // and must render their neutral copy, never a red error.
    renderTab({ whats: ["DATA"] });
    expect(screen.getByText("Objective biz data")).toBeInTheDocument();
    expect(screen.getByText("No pains extracted yet")).toBeInTheDocument();
    expect(screen.getByText("No impacts extracted yet")).toBeInTheDocument();
    expect(screen.queryByText("Failed to load signals")).not.toBeInTheDocument();
  });
});

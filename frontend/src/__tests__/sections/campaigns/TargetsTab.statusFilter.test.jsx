// frontend/src/__tests__/sections/campaigns/TargetsTab.statusFilter.test.jsx
//
// The Target tab's chasing-status filter and the removal of the Reactivate
// action. Real render of TargetsTab through the real ReusableTable — only the
// data hook and the snackbar util are mocked (data sources, not shared
// components); the nested Add-Target modal is stubbed because it is closed and
// never exercised here.
//
// What is pinned:
//  1. Default "In progress" hides the two FINAL states (COMPLETED, STOPPED) and
//     shows every non-final one — including ON_HOLD and CALLBACK_PENDING, which
//     are chases in progress. This proves the filter excludes exactly the two
//     final states, not "everything that isn't IN_PROGRESS".
//  2. "Finished" shows the finals and hides the non-finals.
//  3. "All" shows everything.
//  4. The Reactivate icon (ant "reload") is never rendered, in any filter state.
//  5. A finished row renders NO action at all (no Pause, no Stop) — the
//     isTargeted && isFinalContact early return, proving we do not fall through
//     to the default Pause+Stop branch.
//
// Mirrors CampaignOutcomeModal.callbackDate.test.jsx (vi.mock of the campaigns
// api module + displayError, nested modal stubbed) and the CampaignCard tests
// (mk() factory WITH the ...overrides spread).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

// The real project theme — ReusableTable and the @extended/IconButton read
// custom tokens (palette.primary.lighter, customShadows.*) that a bare
// createTheme() lacks. Assembled the same way themes/index.jsx does (palette +
// customShadows + component overrides). This is a test harness, not a mock.
import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

// ==============================|| MOCKS ||============================== //

// next/font is not executable outside a Next build — stub it (project convention).
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

// Fixed contact set, built in hoisted scope so the vi.mock factory (evaluated
// at import time, before the module body) can close over it. mk() carries the
// ...overrides spread so each row genuinely differs.
const h = vi.hoisted(() => {
  function mk(overrides = {}) {
    return {
      id: `cc-${overrides.contact_name || "x"}`,
      contact_name: "Someone",
      account_name: "Acme Corp",
      department_name: "Sales",
      status: "IN_PROGRESS",
      has_on_hold: false,
      contact: { id: "ct-1", department_name: "Sales" },
      ...overrides,
    };
  }

  const NON_FINAL = [
    mk({ contact_name: "Alice InProgress", status: "IN_PROGRESS" }),
    mk({ contact_name: "Bob OnHold", status: "ON_HOLD" }),
    mk({ contact_name: "Carol Callback", status: "CALLBACK_PENDING" }),
    mk({ contact_name: "Dave Pending", status: "PENDING" }),
  ];
  const FINAL = [
    mk({ contact_name: "Eve Completed", status: "COMPLETED" }),
    mk({ contact_name: "Frank Stopped", status: "STOPPED" }),
  ];

  return { contacts: [...NON_FINAL, ...FINAL] };
});

vi.mock("api/campaigns/campaigns", () => ({
  useGetCampaignContacts: () => ({
    campaignContacts: h.contacts,
    campaignContactsLoading: false,
    campaignContactsError: null,
    mutateCampaignContacts: vi.fn(),
  }),
  pauseTarget: vi.fn(() => Promise.resolve({ success: true })),
  resumeTarget: vi.fn(() => Promise.resolve({ success: true })),
  stopTarget: vi.fn(() => Promise.resolve({ success: true })),
  removeTargets: vi.fn(() => Promise.resolve({ success: true })),
  // Consumed by the (closed) Add-Target modal.
  enrollTarget: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// The Add-Target modal is closed on the tab and not under test; stub it to keep
// the render free of its async-select dependency chain.
vi.mock("sections/campaigns/workspace/AddTargetToCampaignModal", () => ({
  default: () => null,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import TargetsTab from "sections/campaigns/workspace/TargetsTab";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const CAMPAIGN = { status: "ACTIVE", campaign_type: "TARGETED" };

const NON_FINAL_NAMES = [
  "Alice InProgress",
  "Bob OnHold",
  "Carol Callback",
  "Dave Pending",
];
const FINAL_NAMES = ["Eve Completed", "Frank Stopped"];

const base = Palette("light", "default");
const theme = createTheme({
  palette: base.palette,
  customShadows: CustomShadows(base),
});
theme.components = componentsOverride(theme);

function renderTab() {
  return render(
    <ThemeProvider theme={theme}>
      <TargetsTab campaignId="camp-1" campaign={CAMPAIGN} />
    </ThemeProvider>,
  );
}

// Open the MUI Select and pick an option by its visible label.
function selectFilter(label) {
  fireEvent.mouseDown(
    screen.getByRole("combobox", { name: /chasing status/i }),
  );
  fireEvent.click(screen.getByRole("option", { name: label }));
}

function rowFor(name) {
  return screen.getByText(name).closest("tr");
}

// ==============================|| TESTS ||============================== //

describe("TargetsTab — chasing-status filter", () => {
  it("defaults to In progress: shows all non-final states, hides the two finals", () => {
    renderTab();

    // Non-final are all visible — crucially ON_HOLD and CALLBACK_PENDING, which
    // proves only COMPLETED/STOPPED are excluded (not everything != IN_PROGRESS).
    NON_FINAL_NAMES.forEach((name) =>
      expect(screen.getByText(name)).toBeInTheDocument(),
    );
    FINAL_NAMES.forEach((name) =>
      expect(screen.queryByText(name)).toBeNull(),
    );
  });

  it("Finished: shows the final states, hides the non-final ones", () => {
    renderTab();
    selectFilter("Finished");

    FINAL_NAMES.forEach((name) =>
      expect(screen.getByText(name)).toBeInTheDocument(),
    );
    NON_FINAL_NAMES.forEach((name) =>
      expect(screen.queryByText(name)).toBeNull(),
    );
  });

  it("All: shows every contact regardless of state", () => {
    renderTab();
    selectFilter("All");

    [...NON_FINAL_NAMES, ...FINAL_NAMES].forEach((name) =>
      expect(screen.getByText(name)).toBeInTheDocument(),
    );
  });

  it("never renders the Reactivate action (ant reload icon) in any filter state", () => {
    renderTab();
    // Default (In progress).
    expect(screen.queryByRole("img", { name: "reload" })).toBeNull();
    // Finished — the state that used to show Reactivate.
    selectFilter("Finished");
    expect(screen.queryByRole("img", { name: "reload" })).toBeNull();
    // All.
    selectFilter("All");
    expect(screen.queryByRole("img", { name: "reload" })).toBeNull();
  });

  it("a finished row renders NO action, while an in-progress row does", () => {
    renderTab();

    // Non-vacuity: an in-progress row has action buttons (Pause + Stop).
    expect(
      within(rowFor("Alice InProgress")).getAllByRole("button").length,
    ).toBeGreaterThan(0);

    // A finished row has zero action buttons — the isTargeted && isFinalContact
    // early return, NOT a fall-through to the default Pause+Stop branch.
    selectFilter("All");
    expect(within(rowFor("Eve Completed")).queryByRole("button")).toBeNull();
    expect(within(rowFor("Frank Stopped")).queryByRole("button")).toBeNull();
  });
});

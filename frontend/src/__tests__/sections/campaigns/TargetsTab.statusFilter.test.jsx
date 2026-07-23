// frontend/src/__tests__/sections/campaigns/TargetsTab.statusFilter.test.jsx
//
// The Target tab's chasing-status filter and the removal of the Reactivate
// action. Real render of TargetsTab through the real ReusableTable — only the
// data hook and the snackbar util are mocked (data sources, not shared
// components); the nested Add-Target modal is stubbed because it is closed and
// never exercised here.
//
// The filter is a BINARY toggle: "Active" (the 4 non-final states) / "All".
//
// What is pinned:
//  1. A TARGETED campaign defaults to "Active": the two FINAL states (COMPLETED,
//     STOPPED) are hidden and every non-final one is shown — including ON_HOLD
//     and CALLBACK_PENDING, which are chases in progress. This proves the filter
//     excludes exactly the two final states, not "everything != IN_PROGRESS".
//  2. An OUTBOUND campaign defaults to "All": the filter has no meaning in
//     prospecting, so everyone shows (finals included) without any interaction.
//  3. Toggling to "All" reveals everyone; back to "Active" hides the finals.
//  4. The Reactivate icon (ant "reload") is never rendered, in either state.
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

function renderTab(campaignType = "TARGETED") {
  return render(
    <ThemeProvider theme={theme}>
      <TargetsTab
        campaignId="camp-1"
        campaign={{ status: "ACTIVE", campaign_type: campaignType }}
      />
    </ThemeProvider>,
  );
}

// Flip the binary toggle by clicking one of its two buttons.
function toggleTo(label) {
  fireEvent.click(screen.getByRole("button", { name: label }));
}

function rowFor(name) {
  return screen.getByText(name).closest("tr");
}

// ==============================|| TESTS ||============================== //

describe("TargetsTab — chasing-status toggle", () => {
  it("TARGETED defaults to Active: shows all non-final states, hides the two finals", () => {
    renderTab("TARGETED");

    // "Active" is the selected toggle by default.
    expect(screen.getByRole("button", { name: "Active" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    // Non-final are all visible — crucially ON_HOLD and CALLBACK_PENDING, which
    // proves only COMPLETED/STOPPED are excluded (not everything != IN_PROGRESS).
    NON_FINAL_NAMES.forEach((name) =>
      expect(screen.getByText(name)).toBeInTheDocument(),
    );
    FINAL_NAMES.forEach((name) =>
      expect(screen.queryByText(name)).toBeNull(),
    );
  });

  it("OUTBOUND defaults to All: shows every contact without any interaction", () => {
    renderTab("OUTBOUND");

    // "All" is the selected toggle by default for OUTBOUND.
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    [...NON_FINAL_NAMES, ...FINAL_NAMES].forEach((name) =>
      expect(screen.getByText(name)).toBeInTheDocument(),
    );
  });

  it("toggling to All reveals the finals; back to Active hides them again", () => {
    renderTab("TARGETED");

    toggleTo("All");
    [...NON_FINAL_NAMES, ...FINAL_NAMES].forEach((name) =>
      expect(screen.getByText(name)).toBeInTheDocument(),
    );

    toggleTo("Active");
    FINAL_NAMES.forEach((name) =>
      expect(screen.queryByText(name)).toBeNull(),
    );
    NON_FINAL_NAMES.forEach((name) =>
      expect(screen.getByText(name)).toBeInTheDocument(),
    );
  });

  it("never renders the Reactivate action (ant reload icon) in either state", () => {
    renderTab("TARGETED");
    // Default (Active).
    expect(screen.queryByRole("img", { name: "reload" })).toBeNull();
    // All — the view that surfaces finished contacts, which used to show Reactivate.
    toggleTo("All");
    expect(screen.queryByRole("img", { name: "reload" })).toBeNull();
  });

  it("a finished row renders NO action, while an in-progress row does", () => {
    renderTab("TARGETED");

    // Non-vacuity: an in-progress row has action buttons (Pause + Stop).
    expect(
      within(rowFor("Alice InProgress")).getAllByRole("button").length,
    ).toBeGreaterThan(0);

    // A finished row has zero action buttons — the isTargeted && isFinalContact
    // early return, NOT a fall-through to the default Pause+Stop branch.
    toggleTo("All");
    expect(within(rowFor("Eve Completed")).queryByRole("button")).toBeNull();
    expect(within(rowFor("Frank Stopped")).queryByRole("button")).toBeNull();
  });
});

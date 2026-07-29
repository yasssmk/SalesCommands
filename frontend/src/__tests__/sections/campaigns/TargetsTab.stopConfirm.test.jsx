// frontend/src/__tests__/sections/campaigns/TargetsTab.stopConfirm.test.jsx
//
// Stop is irreversible from the Target tab (Reactivate is gone — re-chasing a
// finished contact means re-enrolling it via Add Target), so it is gated behind
// a confirmation dialog. This pins the three-way contract:
//   - clicking Stop opens the dialog and does NOT call stopTarget;
//   - confirming calls stopTarget once with (contactId, campaignId);
//   - cancelling calls nothing and closes the dialog.
//
// Real render of TargetsTab through the real ReusableTable and the real
// confirmation Dialog. Only the data hook and snackbar util are mocked; the
// closed Add-Target modal is stubbed. Follows the AlertCampaignDelete
// confirmation pattern. Mirrors TargetsTab.statusFilter.test.jsx for scaffolding.

import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
  waitFor,
} from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

// Real project theme so ReusableTable / @extended/IconButton resolve their
// custom tokens (test harness, not a mock).
import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

// ==============================|| MOCKS ||============================== //

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

const h = vi.hoisted(() => {
  const contact = {
    id: "cc-1",
    contact_name: "Alice InProgress",
    account_name: "Acme Corp",
    department_name: "Sales",
    status: "IN_PROGRESS",
    has_on_hold: false,
    contact: { id: "ct-1", department_name: "Sales" },
  };
  return { contacts: [contact] };
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
  enrollTarget: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("sections/campaigns/workspace/AddTargetToCampaignModal", () => ({
  default: () => null,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import TargetsTab from "sections/campaigns/workspace/TargetsTab";
import { stopTarget } from "api/campaigns/campaigns";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const base = Palette("light", "default");
const theme = createTheme({
  palette: base.palette,
  customShadows: CustomShadows(base),
});
theme.components = componentsOverride(theme);

function renderTab() {
  return render(
    <ThemeProvider theme={theme}>
      <TargetsTab campaignId="camp-1" campaign={{ status: "ACTIVE", campaign_type: "TARGETED" }} />
    </ThemeProvider>,
  );
}

// The row's Stop control is an icon button (ant "stop" icon).
function clickRowStop() {
  fireEvent.click(screen.getByRole("img", { name: "stop" }).closest("button"));
}

// ==============================|| TESTS ||============================== //

describe("TargetsTab — Stop confirmation", () => {
  it("clicking Stop opens the confirm dialog and does NOT call stopTarget yet", () => {
    renderTab();
    clickRowStop();

    expect(stopTarget).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByText(/are you sure you want to remove/i),
    ).toBeInTheDocument();
    // The contact and account names appear in the prompt.
    expect(within(dialog).getByText(/Alice InProgress — Acme Corp/)).toBeInTheDocument();
    expect(within(dialog).getByText(/from the campaign\?/i)).toBeInTheDocument();
  });

  it("confirming calls stopTarget once with the contact id and campaign id", async () => {
    renderTab();
    clickRowStop();

    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Stop" }));

    await waitFor(() => expect(stopTarget).toHaveBeenCalledTimes(1));
    expect(stopTarget).toHaveBeenCalledWith("cc-1", "camp-1");
  });

  it("cancelling does not call stopTarget and closes the dialog", async () => {
    renderTab();
    clickRowStop();

    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));

    expect(stopTarget).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

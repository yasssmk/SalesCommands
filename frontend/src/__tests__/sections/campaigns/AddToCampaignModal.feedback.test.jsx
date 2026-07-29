// frontend/src/__tests__/sections/campaigns/AddToCampaignModal.feedback.test.jsx
//
// The account/DC wizard must classify enrollment feedback from the reliable signals
// (contacts_enrolled + unreachable_count), never skip_reason:
//   enrolled>0                    → success
//   enrolled=0 && unreachable>0   → WARNING (added, but nobody enrollable)
//   enrolled=0 && unreachable=0   → WARNING (already active)   [was a false success]
//   success:false                 → error

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

const h = vi.hoisted(() => ({ enrollTarget: vi.fn() }));

vi.mock("api/campaigns/campaigns", () => ({
  useGetTargetedCampaign: () => ({ targetedCampaign: { id: "tc-1" }, targetedLoading: false }),
  useGetCampaignContacts: () => ({ campaignContacts: [] }),
  enrollTarget: (...a) => h.enrollTarget(...a),
}));
vi.mock("api/businessData/contacts", () => ({
  useGetContacts: () => ({
    contacts: [{ id: "ct-1", first_name: "A", last_name: "B", email: "a@b.io",
                 account: { id: "acc-1" } }],
    contactsLoading: false,
  }),
}));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionCyclesByAccount: () => ({ cycles: [], cyclesLoading: false }),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
}));

import AddToCampaignModal from "sections/campaigns/AddToCampaignModal";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

const base = Palette("light", "default");
const theme = createTheme({ palette: base.palette, customShadows: CustomShadows(base) });
theme.components = componentsOverride(theme);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function submitAccountMode() {
  render(
    <ThemeProvider theme={theme}>
      <AddToCampaignModal open accountId="acc-1" accountName="Acme" onClose={vi.fn()} onSuccess={vi.fn()} />
    </ThemeProvider>,
  );
  // ACCOUNT mode is the default; step 1 → Next, step 2 → Add to Campaign.
  fireEvent.click(screen.getByRole("button", { name: /^Next$/ }));
  fireEvent.click(screen.getByRole("button", { name: /Add to Campaign/i }));
}

describe("AddToCampaignModal — enrollment feedback", () => {
  it("enrolled>0 → success", async () => {
    h.enrollTarget.mockResolvedValue({ success: true, data: { data: { contacts_enrolled: 1, unreachable_count: 0 } } });
    submitAccountMode();
    await waitFor(() => expect(displaySuccessSnackbar).toHaveBeenCalledTimes(1));
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
  });

  it("enrolled=0 & unreachable>0 → WARNING (not error)", async () => {
    h.enrollTarget.mockResolvedValue({ success: true, data: { data: { contacts_enrolled: 0, unreachable_count: 2 } } });
    submitAccountMode();
    await waitFor(() => expect(displayWarningSnackbar).toHaveBeenCalledTimes(1));
    expect(displayWarningSnackbar.mock.calls[0][0]).toMatch(/no contacts could be enrolled/i);
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
  });

  it("enrolled=0 & unreachable=0 → WARNING (already active), NOT success", async () => {
    h.enrollTarget.mockResolvedValue({ success: true, data: { data: { contacts_enrolled: 0, unreachable_count: 0 } } });
    submitAccountMode();
    await waitFor(() => expect(displayWarningSnackbar).toHaveBeenCalledTimes(1));
    expect(displayWarningSnackbar.mock.calls[0][0]).toMatch(/already active/i);
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
  });

  it("success:false → error", async () => {
    h.enrollTarget.mockResolvedValue({ success: false, error: "boom", status: 400 });
    submitAccountMode();
    await waitFor(() => expect(displayErrorSnackbar).toHaveBeenCalledTimes(1));
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
  });
});

// frontend/src/__tests__/sections/campaigns/AddToCampaignModal.noCalls.test.jsx
//
// The "No calls" toggle in the Add-to-Target modal posts channel_override=
// 'NO_CALLS' on enrollment when checked, and sends no channel_override key when
// left unchecked (the contacts then follow the campaign). Global to the modal,
// so it applies whatever the enrollment mode. Driven in ACCOUNT mode.

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

const base = Palette("light", "default");
const theme = createTheme({ palette: base.palette, customShadows: CustomShadows(base) });
theme.components = componentsOverride(theme);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const OK = {
  success: true,
  data: { data: { contacts_enrolled: 1, no_channel_count: 0, opted_out_count: 0,
                  already_active_count: 0, account_empty: false, strict: false } },
};

function open() {
  render(
    <ThemeProvider theme={theme}>
      <AddToCampaignModal open accountId="acc-1" accountName="Acme" onClose={vi.fn()} onSuccess={vi.fn()} />
    </ThemeProvider>,
  );
  // ACCOUNT mode was removed; CONTACT is the default. Select the single contact,
  // then advance to the confirm step where the toggle lives.
  fireEvent.click(screen.getByText("A B"));
  fireEvent.click(screen.getByRole("button", { name: /^Next$/ }));
}

const lastPayload = () => h.enrollTarget.mock.calls.at(-1)[1];

describe("AddToCampaignModal — No calls toggle", () => {
  it("posts channel_override='NO_CALLS' when the toggle is checked", async () => {
    h.enrollTarget.mockResolvedValue(OK);
    open();
    fireEvent.click(screen.getByLabelText("No calls"));
    fireEvent.click(screen.getByRole("button", { name: /Add to Campaign/i }));

    await waitFor(() => expect(h.enrollTarget).toHaveBeenCalledTimes(1));
    expect(lastPayload().channel_override).toBe("NO_CALLS");
  });

  it("sends no channel_override key when the toggle is left unchecked", async () => {
    h.enrollTarget.mockResolvedValue(OK);
    open();
    fireEvent.click(screen.getByRole("button", { name: /Add to Campaign/i }));

    await waitFor(() => expect(h.enrollTarget).toHaveBeenCalledTimes(1));
    expect("channel_override" in lastPayload()).toBe(false);
  });
});
